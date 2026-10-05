// Azure resources for the payments RAG capstone: Azure OpenAI (chat + embeddings) and Azure AI Search.
//
// Design choices (see infra/README.md):
//  * Keyless: Azure OpenAI has local (key) auth disabled; Azure AI Search accepts Entra ID tokens.
//    The signed-in user gets the roles needed to call both, so no secrets are stored anywhere.
//  * Azure OpenAI and Azure AI Search are in different regions on purpose: the model catalogue lists
//    South India for these models, and AI Search offers its full feature set in Central India.
//  * Search uses the free tier by default ($0, one per subscription, 3 indexes, 50 MB, may be deleted if idle).
//  * Model deployments are small to keep quota needs low: embeddings 10 (10,000 tokens per minute), chat 50
//    (raised from 10 so the 95-question evaluations finish in minutes; capacity caps speed, not cost).

targetScope = 'resourceGroup'

@description('Short lowercase prefix for resource names.')
@maxLength(10)
param namePrefix string = 'payrag'

@description('Region for Azure OpenAI. Check the model region-availability page before changing it.')
param openAiLocation string = 'southindia'

@description('Region for Azure AI Search.')
param searchLocation string = 'centralindia'

@description('Object ID of the user or service principal that will call the services (az ad signed-in-user show --query id -o tsv).')
param principalId string

@description('Principal type for the role assignments.')
@allowed(['User', 'ServicePrincipal', 'Group'])
param principalType string = 'User'

@description('Azure AI Search tier. "free" costs nothing but allows one per subscription; "basic" bills hourly.')
@allowed(['free', 'basic'])
param searchSku string = 'free'

@description('Chat model to deploy.')
param chatModel string = 'gpt-4.1-mini'
param chatModelVersion string = '2025-04-14'
@description('Chat capacity in thousands of tokens per minute.')
param chatCapacity int = 50

@description('Second chat model, used only as the judge in evaluations so that the model that wrote an answer is not the one that grades it. Empty skips it.')
param judgeModel string = 'gpt-5-mini'
param judgeModelVersion string = '2025-08-07'
@description('Judge capacity in thousands of tokens per minute (a reasoning model spends many tokens thinking).')
param judgeCapacity int = 30

@description('Name of a second chat deployment of the same model that uses the stricter content filter policy below. Empty skips it.')
param strictDeploymentName string = 'gpt-4.1-mini-strict'
@description('Capacity of the strict deployment in thousands of tokens per minute.')
param strictCapacity int = 10

@description('Embedding model to deploy (1536 dimensions for text-embedding-3-small).')
param embeddingModel string = 'text-embedding-3-small'
param embeddingModelVersion string = '1'
@description('Embedding capacity in thousands of tokens per minute.')
param embeddingCapacity int = 10

@description('Monthly budget in the subscription currency for this resource group. 0 skips the budget.')
param budgetAmount int = 0
@description('Email that receives budget alerts. Required when budgetAmount > 0.')
param budgetEmail string = ''
@description('First day of the budget period (must be the first of a month).')
param budgetStartDate string = utcNow('yyyy-MM-01')

var unique = uniqueString(resourceGroup().id)
var openAiName = '${namePrefix}-oai-${unique}'
var searchName = '${namePrefix}-search-${unique}'

// Built-in role definition IDs.
var roleOpenAiUser = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd' // Cognitive Services OpenAI User
var roleSearchServiceContributor = '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
var roleSearchIndexDataContributor = '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
var roleSearchIndexDataReader = '1407120a-92aa-4202-b7e9-c0e197c71c8f'

resource openai 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: openAiName
  location: openAiLocation
  kind: 'OpenAI'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: openAiName // required for Entra ID (token) authentication
    disableLocalAuth: true // keyless: API keys are turned off
    publicNetworkAccess: 'Enabled'
  }
}

resource embeddingDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openai
  name: embeddingModel
  sku: {
    name: 'GlobalStandard'
    capacity: embeddingCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: embeddingModel
      version: embeddingModelVersion
    }
  }
}

// Deployments on one account must be created one at a time.
resource chatDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openai
  name: chatModel
  dependsOn: [embeddingDeployment]
  sku: {
    name: 'GlobalStandard'
    capacity: chatCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: chatModel
      version: chatModelVersion
    }
  }
}

// A stricter content filter policy for the payments assistant. It starts from Microsoft's default and
// lowers the harm thresholds from Medium to Low, and turns on the shield for instructions hidden in
// documents (indirect attacks), which the default policy does not include.
resource strictPolicy 'Microsoft.CognitiveServices/accounts/raiPolicies@2024-10-01' = {
  parent: openai
  name: 'payments-strict'
  dependsOn: [judgeDeployment] // child operations on one account must run one at a time
  properties: {
    mode: 'Blocking'
    basePolicyName: 'Microsoft.DefaultV2'
    contentFilters: [
      { name: 'Hate', severityThreshold: 'Low', blocking: true, enabled: true, source: 'Prompt' }
      { name: 'Hate', severityThreshold: 'Low', blocking: true, enabled: true, source: 'Completion' }
      { name: 'Sexual', severityThreshold: 'Low', blocking: true, enabled: true, source: 'Prompt' }
      { name: 'Sexual', severityThreshold: 'Low', blocking: true, enabled: true, source: 'Completion' }
      { name: 'Violence', severityThreshold: 'Low', blocking: true, enabled: true, source: 'Prompt' }
      { name: 'Violence', severityThreshold: 'Low', blocking: true, enabled: true, source: 'Completion' }
      { name: 'Selfharm', severityThreshold: 'Low', blocking: true, enabled: true, source: 'Prompt' }
      { name: 'Selfharm', severityThreshold: 'Low', blocking: true, enabled: true, source: 'Completion' }
      { name: 'Jailbreak', blocking: true, enabled: true, source: 'Prompt' }
      { name: 'Indirect Attack', blocking: true, enabled: true, source: 'Prompt' }
      { name: 'Protected Material Text', blocking: true, enabled: true, source: 'Completion' }
      { name: 'Protected Material Code', blocking: false, enabled: true, source: 'Completion' }
    ]
  }
}

resource strictDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = if (!empty(strictDeploymentName)) {
  parent: openai
  name: strictDeploymentName
  dependsOn: [judgeDeployment]
  sku: {
    name: 'GlobalStandard'
    capacity: strictCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: chatModel
      version: chatModelVersion
    }
    raiPolicyName: strictPolicy.name
  }
}

@description('Larger embedding model (3072 dimensions) used only to compare against the small one. Empty skips it.')
param embeddingLargeName string = 'text-embedding-3-large'
param embeddingLargeVersion string = '1'
@description('Capacity of the large embedding deployment in thousands of tokens per minute.')
param embeddingLargeCapacity int = 30

resource embeddingLargeDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = if (!empty(embeddingLargeName)) {
  parent: openai
  name: embeddingLargeName
  dependsOn: [strictDeployment] // deployments on one account run one at a time
  sku: {
    name: 'Standard'
    capacity: embeddingLargeCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'text-embedding-3-large'
      version: embeddingLargeVersion
    }
  }
}

resource judgeDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = if (!empty(judgeModel)) {
  parent: openai
  name: judgeModel
  dependsOn: [chatDeployment]
  sku: {
    name: 'GlobalStandard'
    capacity: judgeCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: judgeModel
      version: judgeModelVersion
    }
  }
}

resource search 'Microsoft.Search/searchServices@2025-05-01' = {
  name: searchName
  location: searchLocation
  sku: {
    name: searchSku
  }
  properties: {
    replicaCount: 1
    partitionCount: 1
    publicNetworkAccess: 'enabled'
    // The semantic ranker re-reads the top search results with a language model. 'free' allows a
    // monthly allowance of semantic queries at no cost; 'standard' is billed per query.
    semanticSearch: 'free'
    // Accept Entra ID tokens as well as keys. The default is keys only, which would reject role-based calls.
    authOptions: {
      aadOrApiKey: {
        aadAuthFailureMode: 'http401WithBearerChallenge'
      }
    }
  }
}

resource openAiUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: openai
  name: guid(openai.id, principalId, roleOpenAiUser)
  properties: {
    principalId: principalId
    principalType: principalType
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleOpenAiUser)
  }
}

resource searchRoles 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for role in [roleSearchServiceContributor, roleSearchIndexDataContributor, roleSearchIndexDataReader]: {
    scope: search
    name: guid(search.id, principalId, role)
    properties: {
      principalId: principalId
      principalType: principalType
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', role)
    }
  }
]

resource budget 'Microsoft.Consumption/budgets@2023-11-01' = if (budgetAmount > 0 && !empty(budgetEmail)) {
  name: '${namePrefix}-monthly-budget'
  properties: {
    category: 'Cost'
    amount: budgetAmount
    timeGrain: 'Monthly'
    timePeriod: {
      startDate: budgetStartDate
    }
    notifications: {
      actual80: {
        enabled: true
        operator: 'GreaterThan'
        threshold: 80
        contactEmails: [budgetEmail]
      }
      forecast100: {
        enabled: true
        operator: 'GreaterThan'
        threshold: 100
        thresholdType: 'Forecasted'
        contactEmails: [budgetEmail]
      }
    }
  }
}

output openAiEndpoint string = openai.properties.endpoint
output openAiName string = openai.name
output embeddingDeployment string = embeddingDeployment.name
output chatDeployment string = chatDeployment.name
output judgeDeployment string = empty(judgeModel) ? '' : judgeModel
output searchName string = search.name
output searchEndpoint string = 'https://${search.name}.search.windows.net'
