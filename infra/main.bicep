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

@description('Principal ID of the user to grant Storage Blob Data Contributor role (optional)')
param userPrincipalId string = ''

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

// App Service Plan - Premium Plan (Highest tier for production)
resource appServicePlan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: appServicePlanName
  location: functionAppLocation
  sku: {
    name: 'EP3' // Elastic Premium Plan - Highest tier
    tier: 'ElasticPremium'
    size: 'EP3'
    family: 'EP'
    capacity: 1
  }
  kind: 'elastic'
  properties: {
    reserved: true // Required for Linux
    maximumElasticWorkerCount: 20
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
    siteConfig: {
      pythonVersion: '3.11'
      linuxFxVersion: 'Python|3.11'
      alwaysOn: true // Required for Premium plan
      appSettings: [
        {
          name: 'AzureWebJobsStorage__accountName'
          value: storageAccount.name
        }
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
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
        {
          name: 'STORAGE_ACCOUNT_NAME'
          value: storageAccount.name
        }
        {
          name: 'ENABLE_ORYX_BUILD'
          value: 'true'
        }
        {
          name: 'SCM_DO_BUILD_DURING_DEPLOYMENT'
          value: 'true'
        }
      ]
    }
  }
}

// Event Grid System Topic for Storage Account
resource eventGridSystemTopic 'Microsoft.EventGrid/systemTopics@2023-12-15-preview' = {
  name: 'evgt-${storageAccountName}'
  location: storageLocation
  properties: {
    source: storageAccount.id
    topicType: 'Microsoft.Storage.StorageAccounts'
  }
}

// Note: Event Grid subscription is created via postdeploy hook after Function App code is deployed
// This is because the function endpoint must exist before Event Grid can validate it

// Role Definitions
var storageBlobDataOwnerRole = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b')
var storageBlobDataContributorRole = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
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

// Role Assignment: Cosmos DB Data Contributor for deploying user (optional)
// This allows users to browse Cosmos DB data in the Azure Portal
resource userCosmosDbSqlRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2023-04-15' = if (!empty(userPrincipalId)) {
  parent: cosmosDbAccount
  name: guid(cosmosDbAccount.id, userPrincipalId, 'cosmos-contributor-user')
  properties: {
    principalId: userPrincipalId
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

// Role Assignment: Storage Blob Data Contributor for deploying user (optional)
// This allows users to upload documents to the storage account via Azure AD
resource userStorageBlobContributorAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(userPrincipalId)) {
  name: guid(storageAccount.id, userPrincipalId, storageBlobDataContributorRole)
  scope: storageAccount
  properties: {
    principalId: userPrincipalId
    principalType: 'User'
    roleDefinitionId: storageBlobDataContributorRole
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
output eventGridSystemTopicName string = eventGridSystemTopic.name
output resourceGroupName string = resourceGroup().name
output subscriptionId string = subscription().subscriptionId
