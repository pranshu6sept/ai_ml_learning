using './week10.bicep'

// Set before deploying:
//   $env:AZURE_PRINCIPAL_ID = (az ad signed-in-user show --query id -o tsv)
param principalId = readEnvironmentVariable('AZURE_PRINCIPAL_ID')

// Leave empty until the web app is wired to Prompt Shields (it needs the role to call the service).
param appPrincipalId = readEnvironmentVariable('AZURE_W10_APP_PRINCIPAL_ID', '')
