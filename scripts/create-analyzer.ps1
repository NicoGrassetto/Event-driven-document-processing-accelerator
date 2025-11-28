<#
.SYNOPSIS
    Creates a custom AI Content Understanding analyzer from JSON schema.

.DESCRIPTION
    This script creates a custom analyzer in Azure AI Content Understanding service
    using the schema defined in schemas/schema.json. It retrieves the endpoint and
    key from Azure deployment outputs or azd environment.

.NOTES
    Based on: https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/quickstart/use-rest-api
#>

[CmdletBinding()]
param(
    [Parameter()]
    [string]$ResourceGroup,
    
    [Parameter()]
    [string]$DeploymentName,
    
    [Parameter()]
    [string]$SchemaFile = "./schemas/schema.json"
)

$ErrorActionPreference = "Stop"

Write-Host "Creating Custom Content Extraction Analyzer..." -ForegroundColor Blue

# Check if Azure CLI is installed
if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    Write-Host "Error: Azure CLI is not installed. Please install it first." -ForegroundColor Red
    exit 1
}

# Check if user is logged in
try {
    $null = az account show 2>$null
}
catch {
    Write-Host "Error: Not logged in to Azure. Please run 'az login' first." -ForegroundColor Red
    exit 1
}

# Check if schema file exists
if (-not (Test-Path $SchemaFile)) {
    Write-Host "Error: Schema file not found: $SchemaFile" -ForegroundColor Red
    Write-Host "Please create your custom schema at: $SchemaFile" -ForegroundColor Yellow
    exit 1
}

# Load schema and generate analyzer configuration
$schemaBasename = [System.IO.Path]::GetFileNameWithoutExtension($SchemaFile)
$analyzerKind = "extraction"
$analyzerName = "custom-$schemaBasename-analyzer"

# Read schema
$schema = Get-Content $SchemaFile -Raw | ConvertFrom-Json
$schemaDescription = if ($schema.description) { $schema.description } else { "Custom analyzer" }
$analyzerDescription = $schemaDescription

Write-Host "Using schema: $SchemaFile" -ForegroundColor Green
Write-Host "Analyzer name: $analyzerName" -ForegroundColor Blue

# Try to get values from azd environment first
$endpoint = $null
$serviceKey = $null

try {
    Write-Host "Attempting to get configuration from azd environment..." -ForegroundColor Blue
    $azdEnv = azd env get-values 2>$null
    if ($LASTEXITCODE -eq 0 -and $azdEnv) {
        foreach ($line in $azdEnv -split "`n") {
            if ($line -match '^CONTENT_UNDERSTANDING_ENDPOINT="?([^"]+)"?$') {
                $endpoint = $matches[1]
            }
            # Note: azd may not have the key - we'll get it from Azure
        }
    }
}
catch {
    Write-Host "azd environment not available, falling back to deployment outputs" -ForegroundColor Yellow
}

# If not from azd, get from deployment
if (-not $endpoint) {
    Write-Host "Getting deployment outputs..." -ForegroundColor Blue
    
    # Auto-detect resource group and deployment if not provided
    if (-not $ResourceGroup) {
        $ResourceGroup = az group list --query "[?contains(name, 'rg-')].name" -o tsv | Select-Object -First 1
        if (-not $ResourceGroup) {
            Write-Host "Error: Could not auto-detect resource group. Please specify -ResourceGroup parameter." -ForegroundColor Red
            exit 1
        }
        Write-Host "Using resource group: $ResourceGroup" -ForegroundColor Cyan
    }
    
    if (-not $DeploymentName) {
        $DeploymentName = az deployment group list --resource-group $ResourceGroup --query "[0].name" -o tsv
        if (-not $DeploymentName) {
            Write-Host "Error: Could not find deployment in resource group. Please specify -DeploymentName parameter." -ForegroundColor Red
            exit 1
        }
        Write-Host "Using deployment: $DeploymentName" -ForegroundColor Cyan
    }
    
    $endpoint = az deployment group show `
        --resource-group $ResourceGroup `
        --name $DeploymentName `
        --query "properties.outputs.contentUnderstandingEndpoint.value" `
        --output tsv
}

# Get Content Understanding service name and key
$contentUnderstandingName = az deployment group show `
    --resource-group $ResourceGroup `
    --name $DeploymentName `
    --query "properties.outputs.contentUnderstandingName.value" `
    --output tsv

$serviceKey = az cognitiveservices account keys list `
    --resource-group $ResourceGroup `
    --name $contentUnderstandingName `
    --query "key1" `
    --output tsv

if (-not $endpoint -or -not $serviceKey) {
    Write-Host "Error: Could not retrieve endpoint or key from deployment. Make sure the service is deployed." -ForegroundColor Red
    exit 1
}

Write-Host "Retrieved service endpoint and key" -ForegroundColor Green
Write-Host "Endpoint: $endpoint" -ForegroundColor Cyan

# Convert schema.json format to Azure AI Content Understanding format
$fieldSchema = @{
    fields = @{}
}

foreach ($field in $schema.fields) {
    $fieldSchema.fields[$field.fieldKey] = @{
        type = $field.fieldType
        method = "extract"
        description = if ($field.description) { $field.description } else { "" }
    }
}

# Create the analyzer config
$analyzerConfig = @{
    description = $analyzerDescription
    baseAnalyzerId = "prebuilt-documentAnalyzer"
    config = @{
        returnDetails = $true
        enableFormula = $false
        disableContentFiltering = $false
        estimateFieldSourceAndConfidence = $true
        tableFormat = "html"
    }
    fieldSchema = $fieldSchema
}

$analyzerConfigJson = $analyzerConfig | ConvertTo-Json -Depth 10

Write-Host "Analyzer configuration preview:" -ForegroundColor Blue
Write-Host $analyzerConfigJson

# Make the REST API call to create the analyzer
$url = "$($endpoint.TrimEnd('/'))/contentunderstanding/analyzers/$($analyzerName)?api-version=2025-05-01-preview"

$headers = @{
    "Content-Type" = "application/json"
    "Ocp-Apim-Subscription-Key" = $serviceKey
}

try {
    $response = Invoke-RestMethod -Uri $url -Method Put -Headers $headers -Body $analyzerConfigJson
    
    Write-Host "Analyzer '$analyzerName' created successfully!" -ForegroundColor Green
    Write-Host "Response:" -ForegroundColor Blue
    $response | ConvertTo-Json -Depth 10
    
    # Save analyzer info for reference
    $analyzerInfoFile = "analyzer-info-$(Get-Date -Format 'yyyyMMdd-HHmmss').json"
    $response | ConvertTo-Json -Depth 10 | Out-File $analyzerInfoFile
    Write-Host "Analyzer info saved to: $analyzerInfoFile" -ForegroundColor Green
    
    # Create or update environment file
    $envFile = ".analyzer-config"
    @"
# Azure AI Content Understanding Configuration
# Generated by create-analyzer.ps1 on $(Get-Date)

CONTENT_UNDERSTANDING_ENDPOINT=$endpoint
CONTENT_UNDERSTANDING_KEY=$serviceKey
ANALYZER_NAME=$analyzerName
ANALYZER_TYPE=$analyzerKind
"@ | Out-File $envFile -Encoding utf8
    
    Write-Host "Configuration saved to: $envFile" -ForegroundColor Green
    Write-Host "Note: Keep this file secure and don't commit it to version control!" -ForegroundColor Yellow
}
catch {
    Write-Host "Error: Failed to create analyzer." -ForegroundColor Red
    Write-Host "Status: $($_.Exception.Response.StatusCode.value__)" -ForegroundColor Red
    Write-Host "Message: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# List all analyzers to confirm creation
Write-Host "Listing all analyzers..." -ForegroundColor Blue

$listUrl = "$($endpoint.TrimEnd('/'))/contentunderstanding/analyzers?api-version=2025-05-01-preview"
$listHeaders = @{
    "Ocp-Apim-Subscription-Key" = $serviceKey
}

try {
    $listResponse = Invoke-RestMethod -Uri $listUrl -Method Get -Headers $listHeaders
    Write-Host "Available analyzers:" -ForegroundColor Green
    $listResponse | ConvertTo-Json -Depth 10
}
catch {
    Write-Host "Warning: Could not list analyzers" -ForegroundColor Yellow
}

Write-Host "Script completed successfully!" -ForegroundColor Green
Write-Host "You can now use the analyzer '$analyzerName' to analyze documents." -ForegroundColor Blue
Write-Host "Schema used: $SchemaFile" -ForegroundColor Blue
