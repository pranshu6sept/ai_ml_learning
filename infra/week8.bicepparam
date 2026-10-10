using './week8.bicep'

// Set before deploying:
//   $env:AZURE_PRINCIPAL_ID = (az ad signed-in-user show --query id -o tsv)
param principalId = readEnvironmentVariable('AZURE_PRINCIPAL_ID')

// The existing Week 4 resources the app will use.
param openAiAccountName = readEnvironmentVariable('AZURE_OPENAI_ACCOUNT', '')
param searchServiceName = readEnvironmentVariable('AZURE_SEARCH_SERVICE', '')

// F1 is free; B1 is 0.018 USD an hour. Override with $env:AZURE_W8_PLAN_SKU = "B1".
param planSku = readEnvironmentVariable('AZURE_W8_PLAN_SKU', 'F1')

// Week 9 (see the comments in week8.bicep): stage 1 is AZURE_W8_REGISTRY = "true"; stage 3 adds
// AZURE_W8_RUN_CONTAINER = "true" and AZURE_W8_IMAGE_TAG = "<a tag that exists in the registry>".
param createRegistry = readEnvironmentVariable('AZURE_W8_REGISTRY', 'false') == 'true'
param runContainer = readEnvironmentVariable('AZURE_W8_RUN_CONTAINER', 'false') == 'true'
param imageTag = readEnvironmentVariable('AZURE_W8_IMAGE_TAG', 'latest')
