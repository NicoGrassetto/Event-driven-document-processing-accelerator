@description('Location for Storage Account')
param storageLocation string

@description('Location for Cosmos DB')
param cosmosLocation string

@description('Location for Content Understanding service')
param acuLocation string

@description('The name of the Content Extraction service')
param contentUnderstandingName string = 'data-extraction-${uniqueString(resourceGroup().id, deployment().name)}'

@description('The pricing tier for the Content Extraction service')
@allowed(['S0'])
param sku string = 'S0'

@description('Storage account name')
param storageAccountName string = 'storage${uniqueString(resourceGroup().id)}'

@description('Cosmos DB account name')
param cosmosDbAccountName string = 'cosmos-${uniqueString(resourceGroup().id)}'

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


// Outputs
output contentUnderstandingEndpoint string = contentUnderstanding.properties.endpoint
output contentUnderstandingName string = contentUnderstanding.name
output storageAccountName string = storageAccount.name
output cosmosDbEndpoint string = cosmosDbAccount.properties.documentEndpoint
