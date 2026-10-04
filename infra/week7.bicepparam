using './week7.bicep'

// Set AZURE_PRINCIPAL_ID to your Entra object ID before deploying:
//   $env:AZURE_PRINCIPAL_ID = (az ad signed-in-user show --query id -o tsv)
param principalId = readEnvironmentVariable('AZURE_PRINCIPAL_ID')

// The Basic Search service for the indexer demo bills by the hour (about 0.133 USD). Off unless you ask.
//   $env:AZURE_W7_INDEXER_SEARCH = "true"
param deployIndexerSearch = toLower(readEnvironmentVariable('AZURE_W7_INDEXER_SEARCH', 'false')) == 'true'

// Needed only for the indexer demo: the existing Azure OpenAI account the embedding skill will call.
param openAiAccountName = readEnvironmentVariable('AZURE_OPENAI_ACCOUNT', '')
