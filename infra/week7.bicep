// Week 7: Blob Storage for the corpus, a Foundry project, and (optionally) a Basic Azure AI Search service
// that can run an indexer with a managed identity.
//
// Deploy into its OWN resource group so everything here can be deleted without touching the Week 4-6 stack
// (see infra/README.md, "Week 7"):
//   az group create -n rg-payments-rag-w7 -l centralindia
//   az deployment group create -g rg-payments-rag-w7 -f infra/week7.bicep -p infra/week7.bicepparam
//
// Design choices:
//  * Keyless: Blob Storage has shared-key access disabled; people and the search service use Entra ID roles.
//  * The Foundry project is the current model (a CognitiveServices account of kind AIServices plus a child
//    project). No hub. Prompt flow is NOT used: it is retired on 2027-04-20 and works only with hub projects.
//  * The free Search tier cannot use a managed identity for indexers (Microsoft docs: Basic or higher), so the
//    indexer demo needs a separate Basic service. It is OFF by default because it bills by the hour.
//    List price in Central India at the time of writing: 0.133 USD per hour (about 3.19 USD a day).

targetScope = 'resourceGroup'

@description('Short lowercase prefix for resource names.')
@maxLength(10)
param namePrefix string = 'payrag'

@description('Region for Blob Storage and the Basic Search service.')
param location string = 'centralindia'

@description('Region for the Foundry resource. Same region as the Azure OpenAI account so models can be deployed to it.')
param foundryLocation string = 'southindia'

@description('Object ID of the user who will upload documents and call the services (az ad signed-in-user show --query id -o tsv).')
param principalId string

@description('Principal type for the role assignments.')
@allowed(['User', 'ServicePrincipal', 'Group'])
param principalType string = 'User'

@description('Also create a Basic Azure AI Search service with a managed identity, for the indexer demo. Bills hourly: delete the resource group when done.')
param deployIndexerSearch bool = false

@description('Resource group and name of the existing Azure OpenAI account (the embedding skill calls it). Only used when deployIndexerSearch is true.')
param openAiResourceGroup string = 'rg-payments-rag'
param openAiAccountName string = ''

var unique = uniqueString(resourceGroup().id)
var storageName = '${namePrefix}w7st${take(unique, 8)}' // 3-24 lowercase letters and digits
var foundryName = '${namePrefix}-foundry-${take(unique, 8)}'
var projectName = 'payments-rag'
var indexerSearchName = '${namePrefix}-idx-${take(unique, 8)}'

// Built-in role definition IDs.
var roleBlobDataContributor = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
var roleBlobDataReader = '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1'
var roleAzureAiUser = '53ca6127-db72-4b80-b1b0-d745d6d5456d'
var roleSearchServiceContributor = '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
var roleSearchIndexDataContributor = '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
var roleSearchIndexDataReader = '1407120a-92aa-4202-b7e9-c0e197c71c8f'

// --- Blob Storage -----------------------------------------------------------------------------

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: location
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false // keyless: Entra ID roles only
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    accessTier: 'Hot'
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
  properties: {
    // Soft delete lets an indexer notice deleted blobs (native soft-delete detection) and remove their
    // search documents. Deleted blobs are kept for 7 days; the corpus is a few KB, so the cost is nil.
    deleteRetentionPolicy: {
      enabled: true
      days: 7
    }
  }
}

resource corpusContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'corpus'
  properties: {
    publicAccess: 'None'
  }
}

resource userBlobContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storage
  name: guid(storage.id, principalId, roleBlobDataContributor)
  properties: {
    principalId: principalId
    principalType: principalType
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleBlobDataContributor)
  }
}

// --- Foundry resource and project ---------------------------------------------------------------

resource foundry 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: foundryName
  location: foundryLocation
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    allowProjectManagement: true
    customSubDomainName: foundryName
    disableLocalAuth: true // keyless
    publicNetworkAccess: 'Enabled'
  }
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: foundry
  name: projectName
  location: foundryLocation
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    displayName: 'Payments RAG'
    description: 'Evaluations and model catalogue experiments for the payments RAG capstone.'
  }
}

resource userFoundryUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: foundry
  name: guid(foundry.id, principalId, roleAzureAiUser)
  properties: {
    principalId: principalId
    principalType: principalType
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleAzureAiUser)
  }
}

// --- A non-OpenAI judge model on the Foundry resource -------------------------------------------------
// Used to re-grade answers with a model from a different vendor than the one that wrote them.
// Pay per token; 20 = 20,000 tokens and 20 requests per minute, which is the quota this subscription holds.

@description('Deployment name for a Meta Llama judge model on the Foundry resource. Empty skips it.')
param llamaJudgeName string = 'llama-judge'
param llamaJudgeCapacity int = 20

resource llamaJudge 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = if (!empty(llamaJudgeName)) {
  parent: foundry
  name: llamaJudgeName
  dependsOn: [project]
  sku: {
    name: 'GlobalStandard'
    capacity: llamaJudgeCapacity
  }
  properties: {
    model: {
      format: 'Meta'
      name: 'Llama-3.3-70B-Instruct'
      version: '5'
    }
  }
}

// --- A GPT judge for Foundry cloud evaluations ---------------------------------------------------------
// The built-in AI-assisted evaluators (groundedness, relevance, similarity) run inside the project and call
// a model deployed on the same Foundry resource. Pay per token.

@description('Deployment name for the GPT judge used by cloud evaluations. Empty skips it.')
param evalJudgeName string = 'gpt-5-mini'
param evalJudgeCapacity int = 30

resource evalJudge 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = if (!empty(evalJudgeName)) {
  parent: foundry
  name: evalJudgeName
  dependsOn: [llamaJudge] // deployments on one account run one at a time
  sku: {
    name: 'GlobalStandard'
    capacity: evalJudgeCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-5-mini'
      version: '2025-08-07'
    }
  }
}

// --- Optional: Basic Azure AI Search with a managed identity, for indexers ---------------------------

resource indexerSearch 'Microsoft.Search/searchServices@2025-05-01' = if (deployIndexerSearch) {
  name: indexerSearchName
  location: location
  sku: {
    name: 'basic'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    replicaCount: 1
    partitionCount: 1
    publicNetworkAccess: 'enabled'
    semanticSearch: 'disabled'
    authOptions: {
      aadOrApiKey: {
        aadAuthFailureMode: 'http401WithBearerChallenge'
      }
    }
  }
}

// The search service's identity reads the blobs. Its principal ID is only known after deployment,
// so this assignment is created from the service's own identity output.
resource searchBlobReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployIndexerSearch) {
  scope: storage
  name: guid(storage.id, indexerSearchName, roleBlobDataReader)
  properties: {
    principalId: deployIndexerSearch ? indexerSearch!.identity.principalId : ''
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleBlobDataReader)
  }
}

resource userSearchRoles 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for role in [roleSearchServiceContributor, roleSearchIndexDataContributor, roleSearchIndexDataReader]: if (deployIndexerSearch) {
    scope: indexerSearch
    name: guid(indexerSearchName, principalId, role)
    properties: {
      principalId: principalId
      principalType: principalType
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', role)
    }
  }
]

// The embedding skill calls the existing Azure OpenAI account (in another resource group) as the search identity.
module searchOpenAiUser 'modules/openai-user.bicep' = if (deployIndexerSearch && !empty(openAiAccountName)) {
  name: 'search-openai-user'
  scope: resourceGroup(openAiResourceGroup)
  params: {
    openAiAccountName: openAiAccountName
    principalId: deployIndexerSearch ? indexerSearch!.identity.principalId : ''
  }
}

output storageAccountName string = storage.name
output storageBlobEndpoint string = storage.properties.primaryEndpoints.blob
output corpusContainer string = corpusContainer.name
output foundryAccountName string = foundry.name
output foundryProjectName string = project.name
output foundryOpenAiEndpoint string = 'https://${foundryName}.openai.azure.com/'
output llamaJudgeDeployment string = empty(llamaJudgeName) ? '' : llamaJudgeName
output foundryProjectEndpoint string = 'https://${foundryName}.services.ai.azure.com/api/projects/${projectName}'
output evalJudgeDeployment string = empty(evalJudgeName) ? '' : evalJudgeName
output indexerSearchName string = deployIndexerSearch ? indexerSearch!.name : ''
output indexerSearchEndpoint string = deployIndexerSearch ? 'https://${indexerSearchName}.search.windows.net' : ''
