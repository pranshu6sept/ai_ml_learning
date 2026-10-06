// Grants a principal "Search Index Data Reader" (query only) on an existing Azure AI Search service.
// Deployed with a resource-group scope so it can reach a service in a different resource group.

targetScope = 'resourceGroup'

param searchServiceName string
param principalId string

@description('A stable name for the assignment, so repeated deployments update the same one.')
param assignmentKey string = principalId

var roleSearchIndexDataReader = '1407120a-92aa-4202-b7e9-c0e197c71c8f'

resource search 'Microsoft.Search/searchServices@2025-05-01' existing = {
  name: searchServiceName
}

resource reader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: search
  name: guid(search.id, assignmentKey, roleSearchIndexDataReader)
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleSearchIndexDataReader)
  }
}
