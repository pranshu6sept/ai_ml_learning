// Week 8: host the capstone API on Azure App Service, with no keys in code or settings.
//
//   * App Service plan (Linux) + web app with a system-assigned managed identity.
//   * The app calls Azure OpenAI and Azure AI Search as that identity (roles below), never with a key.
//   * The one secret, the API key that protects /ask, lives in Key Vault; the app setting is a Key Vault
//     *reference*, resolved by App Service with the identity. The secret's value is never in this repo,
//     a parameter file or the deployment history: it is set once with `az keyvault secret set`.
//
// The plan defaults to the free F1 tier ($0; 60 CPU minutes a day, no always-on, so the first request after
// idle is slow). B1 is 0.018 USD an hour (about 13 USD a month if left running).
//
// The OpenAI account and the search service are in another resource group (the Week 4 stack); this template
// only adds role assignments on them.

targetScope = 'resourceGroup'

@description('Short lowercase prefix for resource names.')
@maxLength(10)
param namePrefix string = 'payrag'

param location string = resourceGroup().location

@description('Object ID of the signed-in user, who gets Key Vault Secrets Officer to set and read the API key.')
param principalId string

@allowed(['F1', 'B1', 'B2'])
param planSku string = 'F1'

@description('The existing Azure OpenAI account and its resource group.')
param openAiAccountName string
param openAiResourceGroup string = 'rg-payments-rag'
param chatDeployment string = 'gpt-4.1-mini'
param embeddingDeployment string = 'text-embedding-3-small'

@description('The existing Azure AI Search service, its resource group and its index.')
param searchServiceName string
param searchResourceGroup string = 'rg-payments-rag'
param searchIndex string = 'payments-rag'

@description('Name of the Key Vault secret that holds the API key.')
param apiKeySecretName string = 'payrag-api-key'

var unique = uniqueString(resourceGroup().id)
var planName = '${namePrefix}-plan-${take(unique, 8)}'
var appName = '${namePrefix}-api-${take(unique, 8)}'
var vaultName = '${namePrefix}-kv-${take(unique, 8)}'

var roleKeyVaultSecretsUser = '4633458b-17de-408a-b874-0445c86b69e6'
var roleKeyVaultSecretsOfficer = 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7'

resource openai 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: openAiAccountName
  scope: resourceGroup(openAiResourceGroup)
}

resource vault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: vaultName
  location: location
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: tenant().tenantId
    enableRbacAuthorization: true // roles, not access policies
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    publicNetworkAccess: 'Enabled'
  }
}

resource plan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: planName
  location: location
  kind: 'linux'
  sku: {
    name: planSku
  }
  properties: {
    reserved: true // Linux
  }
}

resource app 'Microsoft.Web/sites@2023-12-01' = {
  name: appName
  location: location
  kind: 'app,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.11'
      appCommandLine: 'python -m uvicorn payments_rag.api:app --host 0.0.0.0 --port 8000'
      healthCheckPath: '/health'
      minTlsVersion: '1.2'
      ftpsState: 'Disabled'
      alwaysOn: planSku != 'F1' // not available on the free tier
      appSettings: [
        // Build the Python environment from requirements.txt when the zip is deployed.
        { name: 'SCM_DO_BUILD_DURING_DEPLOYMENT', value: 'true' }
        { name: 'WEBSITES_PORT', value: '8000' }
        // Names and endpoints only: nothing here is a secret.
        { name: 'AZURE_OPENAI_ENDPOINT', value: openai.properties.endpoint }
        { name: 'AZURE_OPENAI_CHAT_DEPLOYMENT', value: chatDeployment }
        { name: 'AZURE_OPENAI_EMBEDDING_DEPLOYMENT', value: embeddingDeployment }
        { name: 'AZURE_SEARCH_ENDPOINT', value: 'https://${searchServiceName}.search.windows.net' }
        { name: 'AZURE_SEARCH_INDEX', value: searchIndex }
        // A reference, not a value: App Service reads the secret with the app's identity.
        { name: 'PAYRAG_API_KEY', value: '@Microsoft.KeyVault(SecretUri=${vault.properties.vaultUri}secrets/${apiKeySecretName}/)' }
      ]
    }
  }
}

// The app reads its one secret.
resource appReadsSecrets 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: vault
  name: guid(vault.id, appName, roleKeyVaultSecretsUser)
  properties: {
    principalId: app.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleKeyVaultSecretsUser)
  }
}

// You set and read the key.
resource userManagesSecrets 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: vault
  name: guid(vault.id, principalId, roleKeyVaultSecretsOfficer)
  properties: {
    principalId: principalId
    principalType: 'User'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleKeyVaultSecretsOfficer)
  }
}

// The app calls the models and searches the index as itself (existing resources, other resource group).
module appOpenAiUser 'modules/openai-user.bicep' = {
  name: 'app-openai-user'
  scope: resourceGroup(openAiResourceGroup)
  params: {
    openAiAccountName: openAiAccountName
    principalId: app.identity.principalId
    assignmentKey: appName
  }
}

module appSearchReader 'modules/search-reader.bicep' = {
  name: 'app-search-reader'
  scope: resourceGroup(searchResourceGroup)
  params: {
    searchServiceName: searchServiceName
    principalId: app.identity.principalId
    assignmentKey: appName
  }
}

output appName string = app.name
output appUrl string = 'https://${app.properties.defaultHostName}'
output vaultName string = vault.name
output apiKeySecretName string = apiKeySecretName
output appPrincipalId string = app.identity.principalId
