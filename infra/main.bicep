@description('Location for Storage Account')
param storageLocation string

@description('Location for Cosmos DB')
param cosmosLocation string

@description('Location for Content Understanding service')
param acuLocation string

@description('Location for Function App')
param functionAppLocation string = storageLocation

@description('The name of the Content Extraction service')
param contentUnderstandingName string = 'data-extraction-${uniqueString(resourceGroup().id, deployment().name)}'

@description('The pricing tier for the Content Extraction service')
@allowed(['S0'])
param sku string = 'S0'

@description('Storage account name')
param storageAccountName string = 'storage${uniqueString(resourceGroup().id)}'

@description('Cosmos DB account name')
param cosmosDbAccountName string = 'cosmos-${uniqueString(resourceGroup().id)}'

@description('Function App name')
param functionAppName string = 'func-docproc-${uniqueString(resourceGroup().id)}'

@description('App Service Plan name')
param appServicePlanName string = 'asp-docproc-${uniqueString(resourceGroup().id)}'

@description('Application Insights name')
param appInsightsName string = 'appi-docproc-${uniqueString(resourceGroup().id)}'

@description('Log Analytics Workspace name')
param logAnalyticsName string = 'log-docproc-${uniqueString(resourceGroup().id)}'

@description('Analyzer name for Content Understanding')
param analyzerName string = 'custom-schema-analyzer'

// Content Extraction service
resource contentUnderstanding 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: contentUnderstandingName
  location: acuLocation
  kind: 'AIServices'
  sku: {
    name: sku
  }
  properties: {
    customSubDomainName: contentUnderstandingName
    disableLocalAuth: false
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
    }
  }
}

// Storage Account for documents
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: storageLocation
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: true
    supportsHttpsTrafficOnly: true
    minimumTlsVersion: 'TLS1_2'
  }
}

// Blob service for the storage account
resource blobServices 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storageAccount
  name: 'default'
}

// Blob container for documents
resource documentContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobServices
  name: 'documents'
  properties: {
    publicAccess: 'None'
  }
}

// Cosmos DB Account
resource cosmosDbAccount 'Microsoft.DocumentDB/databaseAccounts@2023-04-15' = {
  name: cosmosDbAccountName
  location: cosmosLocation
  properties: {
    databaseAccountOfferType: 'Standard'
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    locations: [
      {
        locationName: cosmosLocation
        failoverPriority: 0
      }
    ]
    capabilities: [
      {
        name: 'EnableServerless'
      }
    ]
    enableAutomaticFailover: false
    enableMultipleWriteLocations: false
    enableFreeTier: false
  }
}

// Cosmos DB SQL Database
resource cosmosDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-04-15' = {
  parent: cosmosDbAccount
  name: 'documents'
  properties: {
    resource: {
      id: 'documents'
    }
  }
}

// Cosmos DB Container
resource cosmosContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = {
  parent: cosmosDatabase
  name: 'processed-documents'
  properties: {
    resource: {
      id: 'processed-documents'
      partitionKey: {
        paths: ['/documentId']
        kind: 'Hash'
      }
    }
  }
}

// Log Analytics Workspace for Application Insights
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: logAnalyticsName
  location: functionAppLocation
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// Application Insights for Function App monitoring
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: functionAppLocation
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

// App Service Plan - Flex Consumption
resource appServicePlan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: appServicePlanName
  location: functionAppLocation
  sku: {
    tier: 'FlexConsumption'
    name: 'FC1'
  }
  kind: 'functionapp'
  properties: {
    reserved: true // Required for Linux
  }
}

// Function App with System-Assigned Managed Identity
resource functionApp 'Microsoft.Web/sites@2023-12-01' = {
  name: functionAppName
  location: functionAppLocation
  kind: 'functionapp,linux'
  tags: {
    'azd-service-name': 'api'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    functionAppConfig: {
      deployment: {
        storage: {
          type: 'blobContainer'
          value: '${storageAccount.properties.primaryEndpoints.blob}deploymentpackage'
          authentication: {
            type: 'SystemAssignedIdentity'
          }
        }
      }
      scaleAndConcurrency: {
        maximumInstanceCount: 100
        instanceMemoryMB: 2048
      }
      runtime: {
        name: 'python'
        version: '3.11'
      }
    }
    siteConfig: {
      appSettings: [
        {
          name: 'AzureWebJobsStorage__accountName'
          value: storageAccount.name
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsights.properties.ConnectionString
        }
        {
          name: 'COSMOS_DB_ENDPOINT'
          value: cosmosDbAccount.properties.documentEndpoint
        }
        {
          name: 'COSMOS_DB_DATABASE'
          value: cosmosDatabase.name
        }
        {
          name: 'COSMOS_DB_CONTAINER'
          value: cosmosContainer.name
        }
        {
          name: 'CONTENT_UNDERSTANDING_ENDPOINT'
          value: contentUnderstanding.properties.endpoint
        }
        {
          name: 'ANALYZER_NAME'
          value: analyzerName
        }
      ]
    }
  }
}

// Deployment package container for Flex Consumption
resource deploymentContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobServices
  name: 'deploymentpackage'
  properties: {
    publicAccess: 'None'
  }
}

// Role Definitions
var storageBlobDataOwnerRole = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b')
var cognitiveServicesUserRole = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908')

// Role Assignment: Storage Blob Data Owner (for blob trigger and deployment)
resource storageBlobDataOwnerAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, functionApp.id, storageBlobDataOwnerRole)
  scope: storageAccount
  properties: {
    principalId: functionApp.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: storageBlobDataOwnerRole
  }
}

// Role Assignment: Cosmos DB Data Contributor (for read/write to Cosmos DB)
// Note: This is a SQL role assignment, different from RBAC
resource cosmosDbSqlRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2023-04-15' = {
  parent: cosmosDbAccount
  name: guid(cosmosDbAccount.id, functionApp.id, 'cosmos-contributor')
  properties: {
    principalId: functionApp.identity.principalId
    roleDefinitionId: '${cosmosDbAccount.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002'
    scope: cosmosDbAccount.id
  }
}

// Role Assignment: Cognitive Services User (for ACU access)
resource cognitiveServicesUserAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(contentUnderstanding.id, functionApp.id, cognitiveServicesUserRole)
  scope: contentUnderstanding
  properties: {
    principalId: functionApp.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: cognitiveServicesUserRole
  }
}


// Outputs
output contentUnderstandingEndpoint string = contentUnderstanding.properties.endpoint
output contentUnderstandingName string = contentUnderstanding.name
output storageAccountName string = storageAccount.name
output cosmosDbEndpoint string = cosmosDbAccount.properties.documentEndpoint
output functionAppName string = functionApp.name
output functionAppHostName string = functionApp.properties.defaultHostName
output functionAppPrincipalId string = functionApp.identity.principalId
output appInsightsConnectionString string = appInsights.properties.ConnectionString
output analyzerName string = analyzerName
