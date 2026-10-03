<#
.SYNOPSIS
  Deploys the payments RAG Azure resources (Azure OpenAI + Azure AI Search) and writes a local .env.

.DESCRIPTION
  Run from anywhere:  .\infra\deploy.ps1            (previews with what-if, then asks before deploying)
                      .\infra\deploy.ps1 -WhatIf    (preview only, nothing is created)
  Requires the Azure CLI and `az login`. Nothing is created until you confirm.
#>
param(
    [string]$ResourceGroup = "rg-payments-rag",
    [string]$Location = "centralindia",   # where the resource group's metadata lives
    [switch]$WhatIf
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    throw "Azure CLI not found. Install it with: winget install -e --id Microsoft.AzureCLI  (then reopen the terminal)"
}

$accountJson = az account show 2>$null
if (-not $accountJson) { throw "Not signed in. Run: az login" }
$account = $accountJson | ConvertFrom-Json
Write-Host "Subscription: $($account.name) ($($account.id))"
Write-Host "Signed in as: $($account.user.name)"

$env:AZURE_PRINCIPAL_ID = (az ad signed-in-user show --query id -o tsv)
if (-not $env:AZURE_PRINCIPAL_ID) { throw "Could not read your Entra object ID (az ad signed-in-user show)." }

Write-Host "`nRegistering resource providers (safe to repeat)..."
foreach ($ns in "Microsoft.CognitiveServices", "Microsoft.Search", "Microsoft.Consumption") {
    az provider register --namespace $ns --wait | Out-Null
}

az group create --name $ResourceGroup --location $Location | Out-Null

Write-Host "`nPreview of changes (what-if):"
az deployment group what-if --resource-group $ResourceGroup `
    --template-file "$PSScriptRoot\main.bicep" --parameters "$PSScriptRoot\main.bicepparam"

if ($WhatIf) { Write-Host "`n-WhatIf: stopping before deployment."; return }

$answer = Read-Host "`nDeploy these resources? Azure OpenAI is billed per token; AI Search free tier costs nothing. (y/N)"
if ($answer -notmatch '^(y|yes)$') { Write-Host "Cancelled. Nothing was deployed."; return }

$outputsJson = az deployment group create --resource-group $ResourceGroup `
    --template-file "$PSScriptRoot\main.bicep" --parameters "$PSScriptRoot\main.bicepparam" `
    --query properties.outputs -o json
if ($LASTEXITCODE -ne 0) {
    throw "Deployment failed. Common causes: no Azure OpenAI quota on a free trial (QuotaNotMet), or a free Search service already exists in this subscription. See infra/README.md."
}
$o = $outputsJson | ConvertFrom-Json

$envPath = Join-Path $repoRoot ".env"
@(
    "# Written by infra/deploy.ps1. Contains no secrets (keyless auth). Git-ignored."
    "AZURE_OPENAI_ENDPOINT=$($o.openAiEndpoint.value)"
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT=$($o.embeddingDeployment.value)"
    "AZURE_OPENAI_CHAT_DEPLOYMENT=$($o.chatDeployment.value)"
    "AZURE_SEARCH_ENDPOINT=$($o.searchEndpoint.value)"
    "AZURE_SEARCH_INDEX=payments-rag"
) | Set-Content -Path $envPath -Encoding utf8

Write-Host "`nDeployed. Wrote $envPath"
Write-Host "Role assignments can take a few minutes to take effect. Then run: uv run --all-groups python capstone/evals/azure_smoke_test.py"
