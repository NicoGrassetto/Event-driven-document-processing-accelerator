@description('Location for Storage Account')
param storageLocation string

@description('Location for Cosmos DB')
param cosmosLocation string

// @description('The name of the Content Extraction service')
// param contentUnderstandingName string = 'data-extraction-${uniqueString(resourceGroup().id, deployment().name)}'

// @description('The pricing tier for the Content Extraction service')
// @allowed(['S0'])
// param sku string = 'S0'

@description('Storage account name')
param storageAccountName string = 'storage${uniqueString(resourceGroup().id)}'

@description('Cosmos DB account name')
param cosmosDbAccountName string = 'cosmos-${uniqueString(resourceGroup().id)}'

// @description('Function storage account name')
// param functionStorageAccountName string = 'funcstorage${uniqueString(resourceGroup().id)}'

// @description('Function App name')
// param functionAppName string = 'func-${uniqueString(resourceGroup().id)}'

// Content Extraction service
// resource contentUnderstanding 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
//   name: contentUnderstandingName
//   location: location
//   kind: 'AIServices'
//   sku: {
//     name: sku
//   }
//   properties: {
//     customSubDomainName: contentUnderstandingName
//     disableLocalAuth: false
//     publicNetworkAccess: 'Enabled'
//     networkAcls: {
//       defaultAction: 'Allow'
//     }
//   }
// }

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

// // Function Storage Account (required by Azure Functions runtime)
// resource functionStorageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
//   name: functionStorageAccountName
//   location: location
//   sku: {
//     name: 'Standard_LRS'
//   }
//   kind: 'StorageV2'
//   properties: {
//     accessTier: 'Hot'
//     allowSharedKeyAccess: true  // Required for Function Apps
//     supportsHttpsTrafficOnly: true
//     minimumTlsVersion: 'TLS1_2'
//   }
// }

// // Function App (Consumption Plan - no App Service Plan needed)
// resource functionApp 'Microsoft.Web/sites@2023-01-01' = {
//   name: functionAppName
//   location: location
//   kind: 'functionapp,linux'
//   properties: {
//     reserved: true  // Required for Linux
//     siteConfig: {
//       linuxFxVersion: 'Python|3.11'
//       appSettings: [
//         // Required Function App settings
//         {
//           name: 'AzureWebJobsStorage'
//           value: 'DefaultEndpointsProtocol=https;AccountName=${functionStorageAccount.name};AccountKey=${functionStorageAccount.listKeys().keys[0].value};EndpointSuffix=core.windows.net'
//         }
//         {
//           name: 'WEBSITE_CONTENTAZUREFILECONNECTIONSTRING'
//           value: 'DefaultEndpointsProtocol=https;AccountName=${functionStorageAccount.name};AccountKey=${functionStorageAccount.listKeys().keys[0].value};EndpointSuffix=core.windows.net'
//         }
//         {
//           name: 'WEBSITE_CONTENTSHARE'
//           value: functionAppName
//         }
//         {
//           name: 'FUNCTIONS_EXTENSION_VERSION'
//           value: '~4'
//         }
//         {
//           name: 'FUNCTIONS_WORKER_RUNTIME'
//           value: 'python'
//         }
//         // Application-specific settings for blob trigger and output bindings
//         {
//           name: 'DOCUMENT_STORAGE_CONNECTION_STRING'
//           value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};AccountKey=${storageAccount.listKeys().keys[0].value};EndpointSuffix=core.windows.net'
//         }
//         {
//           name: 'COSMOS_DB_CONNECTION_STRING'
//           value: 'AccountEndpoint=${cosmosDbAccount.properties.documentEndpoint};AccountKey=${cosmosDbAccount.listKeys().primaryMasterKey};'
//         }
//         {
//           name: 'AZURE_AI_SERVICES_ENDPOINT'
//           value: contentUnderstanding.properties.endpoint
//         }
//         {
//           name: 'AZURE_AI_SERVICES_KEY'
//           value: contentUnderstanding.listKeys().key1
//         }
//       ]
//     }
//   }
//   identity: {
//     type: 'SystemAssigned'
//   }
// }

// // Role assignments for secure access
// resource storageBlobContributorRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
//   name: guid(resourceGroup().id, functionApp.id, 'StorageBlobDataContributor')
//   scope: storageAccount
//   properties: {
//     roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
//     principalId: functionApp.identity.principalId
//     principalType: 'ServicePrincipal'
//   }
// }

// resource functionStorageBlobContributorRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
//   name: guid(resourceGroup().id, functionApp.id, 'FuncStorageBlobDataContributor')
//   scope: functionStorageAccount
//   properties: {
//     roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
//     principalId: functionApp.identity.principalId
//     principalType: 'ServicePrincipal'
//   }
// }

// resource cosmosContributorRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
//   name: guid(resourceGroup().id, functionApp.id, 'CosmosDBDataContributor')
//   scope: cosmosDbAccount
//   properties: {
//     roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '00000000-0000-0000-0000-000000000002')
//     principalId: functionApp.identity.principalId
//     principalType: 'ServicePrincipal'
//   }
// }

// resource cognitiveServicesUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
//   name: guid(resourceGroup().id, functionApp.id, 'CognitiveServicesUser')
//   scope: contentUnderstanding
//   properties: {
//     roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908')
//     principalId: functionApp.identity.principalId
//     principalType: 'ServicePrincipal'
//   }
// }

// Outputs
// output contentUnderstandingEndpoint string = contentUnderstanding.properties.endpoint
// output contentUnderstandingName string = contentUnderstanding.name
output storageAccountName string = storageAccount.name
output cosmosDbEndpoint string = cosmosDbAccount.properties.documentEndpoint
// output functionAppName string = functionApp.name
// output functionAppUrl string = 'https://${functionApp.properties.defaultHostName}'
