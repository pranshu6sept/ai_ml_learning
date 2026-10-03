using './main.bicep'

// Set AZURE_PRINCIPAL_ID to your Entra object ID before deploying:
//   $env:AZURE_PRINCIPAL_ID = (az ad signed-in-user show --query id -o tsv)
param principalId = readEnvironmentVariable('AZURE_PRINCIPAL_ID')

// Optional cost guard. Set both to create a monthly budget alert on this resource group.
param budgetAmount = int(readEnvironmentVariable('AZURE_BUDGET_AMOUNT', '0'))
param budgetEmail = readEnvironmentVariable('AZURE_BUDGET_EMAIL', '')
