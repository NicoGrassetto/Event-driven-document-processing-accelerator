@description('The name of the Content Extraction service')
param contentUnderstandingName string = 'content-extraction-${uniqueString(resourceGroup().id)}'

@description('Location for the Content Extraction service')
param location string = resourceGroup().location

@description('The pricing tier for the Content Extraction service')
@allowed(['S0'])
param sku string = 'S0'

@description('Tags to apply to resources')
param tags object = {
  environment: 'test'
  service: 'content-extraction'
}

// Content Extraction service - Using general AI services for preview features
resource contentUnderstanding 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: contentUnderstandingName
  location: location
  tags: tags
  kind: 'AIServices' // General AI services kind for preview features
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

// Output the endpoint and service details for application use
output contentUnderstandingEndpoint string = contentUnderstanding.properties.endpoint
output contentUnderstandingId string = contentUnderstanding.id
output contentUnderstandingName string = contentUnderstanding.name
output contentUnderstandingKey string = contentUnderstanding.listKeys().key1
