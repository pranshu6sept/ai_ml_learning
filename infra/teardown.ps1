<#
.SYNOPSIS
  Deletes the whole resource group (everything deploy.ps1 created) so nothing keeps billing.
#>
param(
    [string]$ResourceGroup = "rg-payments-rag"
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command az -ErrorAction SilentlyContinue)) { throw "Azure CLI not found." }
if (-not (az account show 2>$null)) { throw "Not signed in. Run: az login" }

Write-Host "This permanently deletes resource group '$ResourceGroup' and everything in it:"
az resource list --resource-group $ResourceGroup --query "[].{name:name, type:type}" -o table

$answer = Read-Host "`nType the resource group name to confirm"
if ($answer -ne $ResourceGroup) { Write-Host "Names did not match. Nothing was deleted."; return }

az group delete --name $ResourceGroup --yes --no-wait
Write-Host "Deletion started (runs in the background)."
Write-Host "Azure OpenAI accounts are soft-deleted: to reuse the same name, purge it with"
Write-Host "  az cognitiveservices account list-deleted   then   az cognitiveservices account purge ..."
