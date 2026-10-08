# Azure setup for the payments RAG capstone

Creates **Azure OpenAI** (a chat model and an embedding model) and **Azure AI Search** with Bicep, using
keyless authentication, then checks the whole chain with a smoke test.

| | Resource | Region | Notes |
|---|---|---|---|
| Azure OpenAI | `text-embedding-3-small`, `gpt-4.1-mini` (Global Standard, 10K tokens/min each) | South India | pay per token; API keys turned **off** |
| Azure AI Search | free tier by default | Central India | $0, one per subscription, 3 indexes, 50 MB storage, may be deleted if idle (official limits page, 16 Sep 2026); Entra ID sign-in switched **on** |
| Role assignments | you get: Cognitive Services OpenAI User, Search Service Contributor, Search Index Data Contributor, Search Index Data Reader | | no secrets stored anywhere |

The two services are in different regions on purpose. As of 2 Oct 2026 the Azure OpenAI region table does not list
Central India for any model, while South India lists these models. AI Search has its full feature set in Central
India and only basic support in South India. Check the current tables before changing regions:
[model regions](https://learn.microsoft.com/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure-region-availability),
[Search regions](https://learn.microsoft.com/azure/search/search-region-support).

## Quota on a free trial: checked on this account

Free-trial subscriptions are widely reported to have **zero Azure OpenAI quota**, and the official quota page lists
free trials as N/A for batch quota. So I asked Azure directly. On 2 Oct 2026 this subscription (offer
`FreeTrial_2014-09-01`, spending limit on) reported, for South India
(`az cognitiveservices usage list --location southindia`, after registering `Microsoft.CognitiveServices`):

| Model (Global Standard) | Reported limit |
|---|---|
| `text-embedding-3-small` | 1,000 |
| `gpt-4.1-mini` | 200 |
| `gpt-5-mini` | 500 |
| `gpt-4o-mini`, `gpt-4.1`, `gpt-4o`, `gpt-5` and most others | 0 |

The two models this project deploys have quota (it asks for 10 each), so the trial is not a blocker for them. Only
one Azure OpenAI account is allowed (`OpenAI.S0.AccountCount` is 1). A reported limit isn't a guarantee that a
deployment succeeds, so the first real test is the deploy itself. Quotas can change, so re-check with the command
above if a deployment later fails with `QuotaNotMet`.

**Spending protection** on a free account means your card isn't charged until you upgrade to pay-as-you-go, and
upgrading removes that safeguard. Nothing here requires upgrading.

Optional budget alert before deploying: `$env:AZURE_BUDGET_AMOUNT = "5"; $env:AZURE_BUDGET_EMAIL = "you@example.com"`
(the amount is in your subscription's currency).

## Steps

1. **Install the Azure CLI** (the Bicep compiler is already installed): `winget install -e --id Microsoft.AzureCLI`,
   then reopen the terminal.
2. **Sign in:** `az login` (opens a browser).
3. **Preview, creating nothing:** `.\infra\deploy.ps1 -WhatIf`
4. **Deploy:** `.\infra\deploy.ps1`. It shows the preview again and asks before creating anything, then writes `.env`.
5. **Wait a few minutes** for the role assignments to take effect.
6. **Smoke test:** `uv run --all-groups python capstone/evals/azure_smoke_test.py`. It prints OK or FAIL for each step
   (settings, embedding, index, upload, hybrid search, grounded answer) with the likely cause of any failure.
7. **Rerun the evaluation through Azure:** `uv run --all-groups python capstone/evals/evaluate_azure.py`, and compare
   `azure_eval.md` with the local hybrid result in `embeddings_eval.md`.
8. **When done:** `.\infra\teardown.ps1` deletes the whole resource group so nothing keeps billing.

Use `uv run --all-groups` for Python commands: a plain `uv run` removes the optional dependency groups (Azure,
embeddings, notebooks) from the environment.

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| `QuotaNotMet` or a deployment error mentioning quota | No quota for that model in that region. Re-run the `az cognitiveservices usage list` check above. |
| Search deployment fails: free service already exists | Only one free Search service is allowed per subscription. Delete the old one, or deploy with `searchSku` set to `basic` (billed hourly). |
| `403` right after deploying | Role assignments haven't propagated yet. Wait several minutes and retry. |
| `401` from Search | Role-based access isn't enabled on the service, or you're signed out. The Bicep enables it; run `az login` again. |
| `DeploymentNotFound` / `404` | The deployment name in `.env` doesn't match the portal. |
| Cannot reuse the OpenAI account name after teardown | Azure OpenAI accounts are soft-deleted. Purge: `az cognitiveservices account list-deleted`, then `az cognitiveservices account purge`. |
| `429` | Capacity is limited (chat 50K tokens per minute, embeddings 10K). Wait a minute, or raise `chatCapacity` if you have quota. |

## What has and hasn't been verified

Verified here, on 2 Oct 2026: the Bicep compiles with Bicep CLI 0.47.16 with no warnings; the deployment succeeded on a
free-trial subscription (spending limit on); and `azure_smoke_test.py` passed every step against the live resources
(sign-in, embedding, index, upload, hybrid search, grounded answer), as did `evaluate_azure.py`. Role IDs and region
tables were checked against Microsoft's docs, and quota was read from the account.

Not verified: other subscriptions or regions, the Azure OpenAI v1 API (this uses the `2024-10-21` API version), Azure's
semantic ranker, and long-term behaviour (the free Search tier may be deleted if idle; re-run `deploy.ps1` to recreate).

## Cost notes

Idle resources cost nothing: Azure OpenAI charges per token only, and the free Search tier is $0. So far the smoke
test and evaluations used roughly 100,000 embedding tokens and a couple of chat calls (my estimate, not a measured
figure). To see actual spend, use **Cost Management** in the portal. To remove everything: `.\infra\teardown.ps1`.

## Week 7: Blob Storage, a Foundry project, and an optional indexer service

`week7.bicep` is a separate template for a separate resource group, so the Week 4-6 stack is not touched and everything here can be deleted in one step.

| Resource | Cost (list price) | Notes |
|---|---|---|
| Storage account (Standard LRS) + `corpus` container | a fraction of a cent for a few KB; reads and writes about 0.004-0.055 USD per 10,000 | Shared-key access is off: Entra roles only |
| Foundry resource (kind `AIServices`) + project | no charge for the resource; models and evaluations bill per token | Not a hub project. Prompt flow is retired on 2027-04-20 and is not used |
| Basic Azure AI Search with a managed identity (**optional, off by default**) | **0.133 USD per hour** in Central India (about 3.19 USD a day) | The free tier cannot use a managed identity for indexers, so the indexer demo needs this |

```powershell
$env:AZURE_PRINCIPAL_ID = (az ad signed-in-user show --query id -o tsv)
az provider register --namespace Microsoft.Storage --wait
az group create -n rg-payments-rag-w7 -l centralindia
az deployment group what-if -g rg-payments-rag-w7 -f infra/week7.bicep -p infra/week7.bicepparam
az deployment group create  -g rg-payments-rag-w7 -f infra/week7.bicep -p infra/week7.bicepparam

# Indexer demo (bills hourly): add the Basic service, and tell the template which OpenAI account to grant
$env:AZURE_W7_INDEXER_SEARCH = "true"; $env:AZURE_OPENAI_ACCOUNT = "<your openai account name>"

# Delete everything from Week 7 (the Week 4-6 stack is untouched):
az group delete -n rg-payments-rag-w7 --yes --no-wait
```

`what-if` shows one "Unsupported" line when the indexer service is on: that is the cross-resource-group OpenAI role assignment, whose principal ID only exists after the search service is created.

**Deleting and recreating the Basic service:** the indexer runs as a **user-assigned managed identity** that `week7.bicep` creates once (with its Blob Reader and OpenAI User roles), so deleting and recreating the search service touches no role assignment. Two things to know:

- A deleted search service's name stays reserved for a few minutes. Redeploying 2.7 minutes after a delete failed with `ServiceDeleting`; about 6 minutes after, it worked. Retry rather than changing the name.
- The identity's role on the Azure OpenAI account lives in another resource group, so deleting `rg-payments-rag-w7` removes the storage role but is expected to leave that one behind. Remove it by assignment ID (assignee lookups fail for a deleted identity):

```powershell
az role assignment list --scope <openai account id> --query "[?principalType=='ServicePrincipal'].id" -o tsv
az role assignment delete --ids <id>   # check first that it is the deleted indexer identity's
```

Add `AZURE_W7_INDEXER_IDENTITY_ID=<identity resource id>` (the `indexerIdentityResourceId` deployment output) to `.env` so `run_blob_indexer.py` uses it.

## Week 8: the API on App Service, with a Key Vault secret

`week8.bicep` is a third template, with its own resource group (`rg-payments-rag-w8`). It adds a Linux App Service plan (free F1 by default), a web app with a system-assigned managed identity, and a Key Vault, and gives the app's identity only the roles it needs on the existing OpenAI account and search service.

```powershell
$env:AZURE_PRINCIPAL_ID = (az ad signed-in-user show --query id -o tsv)
$env:AZURE_OPENAI_ACCOUNT = "<your openai account name>"
$env:AZURE_SEARCH_SERVICE = "<your search service name>"
az provider register --namespace Microsoft.Web --wait; az provider register --namespace Microsoft.KeyVault --wait
az group create -n rg-payments-rag-w8 -l centralindia
az deployment group create -g rg-payments-rag-w8 -f infra/week8.bicep -p infra/week8.bicepparam

# Set the API key once (the value never goes in the repo): generate it, write it from a file, delete the file.
az keyvault secret set --vault-name <vault> --name payrag-api-key --file key.txt

# Build and deploy the code.
uv run python capstone/deploy/build_zip.py
az webapp deploy -g rg-payments-rag-w8 -n <app> --src-path capstone/deploy/dist/app.zip --type zip
# The command can look stuck or fail without a cause while the server succeeds: check
az webapp log deployment show -g rg-payments-rag-w8 -n <app>
```

Plan: F1 is free (no always-on, a small shared instance); `$env:AZURE_W8_PLAN_SKU = "B1"` is 0.018 USD an hour. A Key Vault reference needs the secret to exist before the app starts, or a restart afterwards. To remove everything: `az group delete -n rg-payments-rag-w8 --yes --no-wait`; the app's role assignments on the OpenAI account and the search service are in the other resource group and stay behind as orphans (delete them by assignment ID).

## Week 8: Azure ML (`week8-ml.bicep`, resource group `rg-payments-rag-w8ml`)

```powershell
az deployment group create -g rg-payments-rag-w8ml -f infra/week8-ml.bicep   # workspace + cpu-cluster (scales to 0)
cd classical_ml
az ml job create -f azureml/job.yml --web=false          # trains, logs metrics, saves an MLflow model
az ml model create -n fraud-lightgbm --type mlflow_model --path azureml://jobs/<job>/outputs/model
az ml online-endpoint create -f azureml/endpoint.yml
az ml online-deployment create -f azureml/deployment.yml --all-traffic
az ml online-endpoint invoke -n payrag-fraud --request-file azureml/sample-request.json
az ml online-endpoint delete -n payrag-fraud --yes       # an endpoint bills per instance-hour until deleted
```

Needs the resource providers PolicyInsights, Cdn, Network, ContainerService and ManagedIdentity registered. The workspace's Key Vault must use access policies, not RBAC. Check the registered model's `requirements.txt` lists `azureml-ai-monitoring` before deploying. The endpoint's image build can fail on pypi timeouts; retrying worked.
