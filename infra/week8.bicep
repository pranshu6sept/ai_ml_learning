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
//
// Week 9 adds `hosting = 'container'`: the app runs the image from `capstone/Dockerfile`, pulled from a Basic
// container registry (about 5 USD a month) with the app's own identity (no registry password). GitHub Actions
// pushes the image and points the app at it, signing in as a user-assigned identity through a federated
// credential (OIDC): GitHub holds no Azure secret. The default stays `zip`, the Week 8 setup.

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

@description('zip: App Service builds the Python app from a zip (Week 8). container: it runs the image from the registry.')
@allowed(['zip', 'container'])
param hosting string = 'zip'

@description('GitHub repository (owner/name) whose workflow may deploy. Container hosting only.')
param githubRepo string = 'pranshu6sept/ai_ml_learning'

@description('Branch whose pushes may deploy (the federated credential trusts this branch only).')
param githubBranch string = 'main'

@description('Image tag the app runs; the workflow replaces it with the commit SHA on each deploy.')
param imageTag string = 'latest'

var unique = uniqueString(resourceGroup().id)
var planName = '${namePrefix}-plan-${take(unique, 8)}'
var appName = '${namePrefix}-api-${take(unique, 8)}'
var vaultName = '${namePrefix}-kv-${take(unique, 8)}'
var registryName = '${namePrefix}acr${take(unique, 10)}' // letters and digits only
var deployerName = '${namePrefix}-github-deployer'
var imageName = 'payrag-api'
var container = hosting == 'container'

var roleKeyVaultSecretsUser = '4633458b-17de-408a-b874-0445c86b69e6'
var roleKeyVaultSecretsOfficer = 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7'
var roleAcrPull = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
var roleAcrPush = '8311e382-0749-4cb8-b61a-304f252e45ec'
var roleWebsiteContributor = 'de139f84-1756-47ae-9be6-808fbbe84772'

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

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' = if (container) {
  name: registryName
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false // pulls and pushes use Entra identities, never the admin password
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
      linuxFxVersion: container ? 'DOCKER|${registryName}.azurecr.io/${imageName}:${imageTag}' : 'PYTHON|3.11'
      // The image has its own start command (CMD in the Dockerfile).
      appCommandLine: container ? '' : 'python -m uvicorn payments_rag.api:app --host 0.0.0.0 --port 8000'
      acrUseManagedIdentityCreds: container // pull with the app's system-assigned identity
      healthCheckPath: '/health'
      minTlsVersion: '1.2'
      ftpsState: 'Disabled'
      alwaysOn: planSku != 'F1' // not available on the free tier
      appSettings: concat(container ? [] : [
        // Build the Python environment from requirements.txt when the zip is deployed.
        { name: 'SCM_DO_BUILD_DURING_DEPLOYMENT', value: 'true' }
      ], [
        { name: 'WEBSITES_PORT', value: '8000' }
        // Names and endpoints only: nothing here is a secret.
        { name: 'AZURE_OPENAI_ENDPOINT', value: openai.properties.endpoint }
        { name: 'AZURE_OPENAI_CHAT_DEPLOYMENT', value: chatDeployment }
        { name: 'AZURE_OPENAI_EMBEDDING_DEPLOYMENT', value: embeddingDeployment }
        { name: 'AZURE_SEARCH_ENDPOINT', value: 'https://${searchServiceName}.search.windows.net' }
        { name: 'AZURE_SEARCH_INDEX', value: searchIndex }
        // A reference, not a value: App Service reads the secret with the app's identity.
        { name: 'PAYRAG_API_KEY', value: '@Microsoft.KeyVault(SecretUri=${vault.properties.vaultUri}secrets/${apiKeySecretName}/)' }
      ])
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

// The app pulls its image.
resource appPullsImages 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (container) {
  scope: registry
  name: guid(registryName, appName, roleAcrPull)
  properties: {
    principalId: app.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleAcrPull)
  }
}

// The identity GitHub Actions signs in as. Only a workflow run for a push to `githubBranch` of `githubRepo`
// can get a token for it, and it may only push images and change this one app.
resource deployer 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = if (container) {
  name: deployerName
  location: location
}

resource deployerTrustsGithub 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = if (container) {
  parent: deployer
  name: 'github-${githubBranch}'
  properties: {
    issuer: 'https://token.actions.githubusercontent.com'
    subject: 'repo:${githubRepo}:ref:refs/heads/${githubBranch}'
    audiences: ['api://AzureADTokenExchange']
  }
}

resource deployerPushesImages 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (container) {
  scope: registry
  name: guid(registryName, deployerName, roleAcrPush)
  properties: {
    principalId: deployer!.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleAcrPush)
  }
}

resource deployerUpdatesApp 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (container) {
  scope: app
  name: guid(app.id, deployerName, roleWebsiteContributor)
  properties: {
    principalId: deployer!.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleWebsiteContributor)
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
// For the GitHub repository variables (container hosting; none of these is a secret).
output registryName string = container ? registryName : ''
output deployerClientId string = container ? deployer!.properties.clientId : ''
output tenantId string = tenant().tenantId
output subscriptionId string = subscription().subscriptionId
output resourceGroupName string = resourceGroup().name
