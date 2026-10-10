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

// Week 9: run the app from a container image and let GitHub Actions deploy it. Staged on purpose, so the
// live app never points at an image that is not there yet:
//   1. createRegistry = true               adds the registry, the deployer identity and their roles; the app
//                                          keeps running from the zip
//   2. push the first image                (docker push, or the workflow)
//   3. createRegistry + runContainer = true, imageTag = <a tag that exists>   switches the app to the image
// To go back to the zip: runContainer = false, then deploy the zip as in infra/README.md.
@description('Create the container registry (Basic, about 5 USD a month), the GitHub deployer identity and the roles.')
param createRegistry bool = false

@description('Run the app from the registry image instead of the zip. Needs createRegistry and an image with imageTag.')
param runContainer bool = false

@description('GitHub repository (owner/name) whose workflow on the main branch may deploy.')
param githubRepo string = 'pranshu6sept/ai_ml_learning'

param imageName string = 'payrag-api'

@description('The image tag the app runs. The workflow sets the commit SHA; this only has to exist when runContainer is true.')
param imageTag string = 'latest'

var unique = uniqueString(resourceGroup().id)
var planName = '${namePrefix}-plan-${take(unique, 8)}'
var appName = '${namePrefix}-api-${take(unique, 8)}'
var vaultName = '${namePrefix}-kv-${take(unique, 8)}'
var registryName = '${namePrefix}acr${take(unique, 8)}' // letters and digits only
var registryLoginServer = '${registryName}.azurecr.io'
var deployerName = '${namePrefix}-github-deployer'

var roleKeyVaultSecretsUser = '4633458b-17de-408a-b874-0445c86b69e6'
var roleKeyVaultSecretsOfficer = 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7'
var roleAcrPull = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
var roleAcrPush = '8311e382-0749-4cb8-b61a-304f252e45ec'
var roleWebsiteContributor = 'de139f84-1756-47ae-9be6-808fbbe84772'

// Settings that differ between the zip (App Service builds the Python environment) and the image.
var hostingSettings = runContainer
  ? [{ name: 'WEBSITES_ENABLE_APP_SERVICE_STORAGE', value: 'false' }]
  : [{ name: 'SCM_DO_BUILD_DURING_DEPLOYMENT', value: 'true' }]

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
      linuxFxVersion: runContainer ? 'DOCKER|${registryLoginServer}/${imageName}:${imageTag}' : 'PYTHON|3.11'
      acrUseManagedIdentityCreds: runContainer // pull with the app's own identity: no registry password
      // The image starts uvicorn itself (the Dockerfile's CMD); the zip needs the command.
      appCommandLine: runContainer ? '' : 'python -m uvicorn payments_rag.api:app --host 0.0.0.0 --port 8000'
      healthCheckPath: '/health'
      minTlsVersion: '1.2'
      ftpsState: 'Disabled'
      alwaysOn: planSku != 'F1' // not available on the free tier
      appSettings: concat(hostingSettings, [
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

// ---- Week 9: container registry and the GitHub deployer (only when createRegistry) ----

// Basic is the cheapest tier (about 5 USD a month, 10 GB included). No admin user (anonymous pull is off by default):
// the app pulls as itself, the workflow pushes as the deployer identity.
resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' = if (createRegistry) {
  name: registryName
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'
  }
}

resource appPullsImages 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (createRegistry) {
  scope: registry
  name: guid(registry.id, appName, roleAcrPull)
  properties: {
    principalId: app.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleAcrPull)
  }
}

// The identity GitHub Actions signs in as. It holds no secret: Entra ID trusts a token from GitHub's OIDC
// issuer only when its subject is exactly "a workflow run for a push to main of this repository", so a fork,
// another branch or a pull request cannot sign in as it.
resource deployer 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = if (createRegistry) {
  name: deployerName
  location: location
}

resource deployerFromGithubMain 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = if (createRegistry) {
  parent: deployer
  name: 'github-main'
  properties: {
    issuer: 'https://token.actions.githubusercontent.com'
    subject: 'repo:${githubRepo}:ref:refs/heads/main'
    audiences: ['api://AzureADTokenExchange']
  }
}

// It may push images to this registry and manage this one web app, nothing else.
resource deployerPushesImages 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (createRegistry) {
  scope: registry
  name: guid(registry.id, deployerName, roleAcrPush)
  properties: {
    principalId: deployer!.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleAcrPush)
  }
}

resource deployerManagesApp 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (createRegistry) {
  scope: app
  name: guid(app.id, deployerName, roleWebsiteContributor)
  properties: {
    principalId: deployer!.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleWebsiteContributor)
  }
}

output registryName string = createRegistry ? registryName : ''
output deployerClientId string = createRegistry ? deployer!.properties.clientId : ''
output tenantId string = tenant().tenantId
output subscriptionId string = subscription().subscriptionId
output resourceGroupName string = resourceGroup().name
output appName string = app.name
output appUrl string = 'https://${app.properties.defaultHostName}'
output vaultName string = vault.name
output apiKeySecretName string = apiKeySecretName
output appPrincipalId string = app.identity.principalId
