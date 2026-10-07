// Week 8, Azure ML half: a workspace, and a compute cluster for training jobs.
//
// Own resource group (rg-payments-rag-w8ml), so everything here, including the endpoint created later with the
// `az ml` CLI, is removed with one `az group delete`.
//
// Cost: the workspace and its storage, key vault and Application Insights are close to free. The cluster scales
// to ZERO nodes when idle, so it bills (0.062 USD an hour for Standard_D2as_v4 at list price) only while a job
// runs. The managed online endpoint is the expensive piece and is created separately, on purpose.
//
// Deviation to know about: the workspace's storage account keeps shared-key access, which Azure ML needs by
// default for its datastores. The other stacks in this repo are keyless.

targetScope = 'resourceGroup'

@description('Short lowercase prefix for resource names.')
@maxLength(10)
param namePrefix string = 'payrag'

param location string = resourceGroup().location

@description('VM size for training. Small and cheap; the quota here is 4 vCPUs per family.')
param trainingVmSize string = 'Standard_D2as_v4'

var unique = uniqueString(resourceGroup().id)
var storageName = '${namePrefix}ml${take(unique, 10)}'
var vaultName = '${namePrefix}-mlkv-${take(unique, 6)}'
var logsName = '${namePrefix}-logs-${take(unique, 6)}'
var insightsName = '${namePrefix}-ai-${take(unique, 6)}'
var workspaceName = '${namePrefix}-ml-${take(unique, 6)}'

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    supportsHttpsTrafficOnly: true
  }
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
    // Access policies, not RBAC: Azure ML adds an access policy for its own identity when it creates the
    // workspace and fails against an RBAC-only vault (the other vaults in this repo use RBAC).
    enableRbacAuthorization: false
    accessPolicies: []
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
  }
}

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logsName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource insights 'Microsoft.Insights/components@2020-02-02' = {
  name: insightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logs.id
  }
}

resource workspace 'Microsoft.MachineLearningServices/workspaces@2024-10-01' = {
  name: workspaceName
  location: location
  kind: 'Default'
  identity: {
    type: 'SystemAssigned'
  }
  sku: {
    name: 'Basic'
    tier: 'Basic'
  }
  properties: {
    friendlyName: 'payments-rag ml'
    storageAccount: storage.id
    keyVault: vault.id
    applicationInsights: insights.id
    publicNetworkAccess: 'Enabled'
    // The container registry is created by Azure ML the first time an environment image is built.
  }
}

resource cluster 'Microsoft.MachineLearningServices/workspaces/computes@2024-10-01' = {
  parent: workspace
  name: 'cpu-cluster'
  location: location
  properties: {
    computeType: 'AmlCompute'
    properties: {
      vmSize: trainingVmSize
      vmPriority: 'Dedicated'
      scaleSettings: {
        minNodeCount: 0 // idle = free
        maxNodeCount: 1
        nodeIdleTimeBeforeScaleDown: 'PT2M'
      }
    }
  }
}

output workspaceName string = workspace.name
output resourceGroup string = resourceGroup().name
