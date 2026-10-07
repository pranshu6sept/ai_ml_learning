using './week8.bicep'

// Set before deploying:
//   $env:AZURE_PRINCIPAL_ID = (az ad signed-in-user show --query id -o tsv)
param principalId = readEnvironmentVariable('AZURE_PRINCIPAL_ID')

// The existing Week 4 resources the app will use.
param openAiAccountName = readEnvironmentVariable('AZURE_OPENAI_ACCOUNT', '')
param searchServiceName = readEnvironmentVariable('AZURE_SEARCH_SERVICE', '')

// F1 is free; B1 is 0.018 USD an hour. Override with $env:AZURE_W8_PLAN_SKU = "B1".
param planSku = readEnvironmentVariable('AZURE_W8_PLAN_SKU', 'F1')

// zip (Week 8) or container (Week 9: registry + GitHub OIDC deployer). Override with $env:AZURE_W8_HOSTING = "container".
param hosting = readEnvironmentVariable('AZURE_W8_HOSTING', 'zip')
