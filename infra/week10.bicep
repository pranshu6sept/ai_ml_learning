// Week 10: Azure AI Content Safety for Prompt Shields, on the free tier, keyless.
//
//   * One Content Safety account, SKU F0 (free; Prompt Shields allows 5 requests a second on it).
//     Groundedness detection is NOT available on F0 and not offered in South India, so it is not used.
//   * Key authentication is disabled: callers use a Microsoft Entra ID token. The account needs a custom
//     subdomain for that.
//   * "Cognitive Services User" for you (to run the evaluation) and, optionally, for the web app's identity.
//
// Region: Microsoft Learn's region table lists Prompt Shields in South India (not Central India), which is
// also where the models run, so the questions stay in one region.

targetScope = 'resourceGroup'

@description('Short lowercase prefix for resource names.')
@maxLength(10)
param namePrefix string = 'payrag'

param location string = 'southindia'

@description('Object ID of the signed-in user, who may call the service.')
param principalId string

@description('Object ID of the web app identity that may call the service. Leave empty until the app uses it.')
param appPrincipalId string = ''

var unique = uniqueString(resourceGroup().id)
var accountName = '${namePrefix}-cs-${take(unique, 8)}'
var roleCognitiveServicesUser = 'a97b65f3-24c7-4388-baec-2e87135dc908'

resource contentSafety 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: accountName
  location: location
  kind: 'ContentSafety'
  sku: {
    name: 'F0'
  }
  properties: {
    customSubDomainName: accountName
    disableLocalAuth: true // Entra ID only: there is no key to leak
    publicNetworkAccess: 'Enabled'
  }
}

resource userCallsService 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: contentSafety
  name: guid(contentSafety.id, principalId, roleCognitiveServicesUser)
  properties: {
    principalId: principalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleCognitiveServicesUser)
  }
}

resource appCallsService 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(appPrincipalId)) {
  scope: contentSafety
  name: guid(contentSafety.id, appPrincipalId, roleCognitiveServicesUser)
  properties: {
    principalId: appPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleCognitiveServicesUser)
  }
}

output accountName string = contentSafety.name
output endpoint string = contentSafety.properties.endpoint
