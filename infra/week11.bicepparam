using './week11.bicep'

// Set before deploying:
//   $env:AZURE_W11_APP_PRINCIPAL_ID = (az webapp identity show -g rg-payments-rag-w8 -n <app> --query principalId -o tsv)
param appPrincipalId = readEnvironmentVariable('AZURE_W11_APP_PRINCIPAL_ID')

// Optional. Empty: alerts show in the portal but nobody is emailed. 1,000 alert emails a month are free.
param alertEmail = readEnvironmentVariable('AZURE_W11_ALERT_EMAIL', '')
