// Grants a principal "Cognitive Services OpenAI User" on an existing Azure OpenAI account.
// Deployed with a resource-group scope so it can reach an account in a different resource group.

targetScope = 'resourceGroup'

param openAiAccountName string
param principalId string

@description('A stable name for the assignment (for example the identity name), so repeated deployments update the same one.')
param assignmentKey string = principalId

var roleOpenAiUser = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd' // Cognitive Services OpenAI User

resource openai 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: openAiAccountName
}

resource openAiUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: openai
  name: guid(openai.id, assignmentKey, roleOpenAiUser)
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleOpenAiUser)
  }
}
