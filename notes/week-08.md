# Week 8: hosting and identity (in progress)

Roadmap items: Azure ML (workspace, compute, jobs, model registry, a managed endpoint that serves the Week 3 model); deploy the capstone API to App Service or Functions; Key Vault and managed identity with no keys in code or env files; book the AI-102 exam; **deliverable: the capstone reachable at a public URL, keyless auth to Azure services.**

This file records what is done and measured. The Azure ML half is not started; see "Not done".

## Status against the roadmap

| Item | Status |
|---|---|
| Deploy the capstone API to App Service | **Done**: FastAPI app on a Linux App Service (free F1 plan), public HTTPS URL |
| Key Vault and managed identity, no keys in code or env files | **Done and audited** (below) |
| Deliverable: public URL with keyless auth to Azure services | **Done**, with the limits listed below |
| Azure ML: workspace, compute, jobs, registry, managed endpoint for the Week 3 model | **Not started** (needs your decision on cost; see the end) |
| Book the AI-102 exam date | **Yours to do**; I cannot book it |

## The API (`payments_rag/api.py`)

`GET /health`, `POST /ask`, `POST /feedback`. It serves the plain `ask` pipeline (hybrid search with the semantic ranker, a quote-verified answerability check, a cited answer or a refusal), which measured better and faster than the graph in Week 6. The app is built from an injected answering function, so the HTTP layer is tested without Azure (18 tests: validation, auth, rate limit, error handling, feedback).

Because a public URL in front of a paid model is a spending risk, three guards run before any model call:
- the question must be 1 to 1000 characters;
- a **global** rate limit (30 requests a minute for the process); it is per process, so several instances multiply it;
- an `X-API-Key` header, compared in constant time, required whenever `PAYRAG_API_KEY` is set. The key check runs before body validation, so a stranger gets 401 and learns nothing about the request format. `/health` stays open for probes.

A failure inside the pipeline is a 502 with a generic message; the cause (an endpoint name, a model error) goes to the log, not to the caller. `/feedback` stores ratings in memory only (lost on restart, not shared between instances): a placeholder until Week 11 stores them with the trace ID.

## Hosting and identity (`infra/week8.bicep`, own resource group `rg-payments-rag-w8`)

| Piece | What it is |
|---|---|
| App Service plan | Linux, **F1 (free)**. Not always-on, 1 GB, and a daily CPU-time allowance, so the first request after idle is slow. B1 would be 0.018 USD an hour (about 13 USD a month if left running); the template takes `B1` as a parameter |
| Web app | Python 3.11, HTTPS only, TLS 1.2 minimum, FTPS off, a `/health` check, system-assigned managed identity |
| Key Vault | RBAC authorization (no access policies), soft delete 7 days. Holds one secret, the API key |
| App setting `PAYRAG_API_KEY` | A Key Vault **reference**, not a value; App Service reads the secret with the app's identity |
| The app's roles | Key Vault Secrets User (the vault), Cognitive Services OpenAI User (the OpenAI account), **Search Index Data Reader** (the search service: query only) |
| Your role | Key Vault Secrets Officer on the vault, to set and read the key |

The secret value never appears in the repo, the template, a parameter file or the deployment history: I generated it locally, wrote it to the vault from a temporary file (deleted at once), and never printed it. You read it with `az keyvault secret show --vault-name <vault> --name payrag-api-key --query value -o tsv`.

The zip that App Service runs is built by `capstone/deploy/build_zip.py` from the package source plus `requirements.txt` (compiled from `requirements.in`: 42 packages, no torch, xgboost or notebooks; 22 files, 50 KB). A test checks the zip contains no `.env`, tests or caches. App Service builds the environment itself (Oryx, about two minutes).

**Audit of the deployed app** (read from Azure, not assumed):
- the app settings contain endpoints, deployment names and the Key Vault reference, and no secret value;
- the Key Vault reference reads `Resolved`;
- the app's identity holds exactly the three roles above;
- the Azure OpenAI account has key authentication disabled, so the only way in is an Entra identity;
- without the key `/ask` returns 401; with the key from the vault it returned a cited answer.

## Measured on the hosted app

Ten answerable golden questions, sent one at a time (2.5 s apart), against the live URL:

| | Median | p95 |
|---|---|---|
| Server-side (`latency_ms`) | 3.3 s | 5.2 s |
| Client-side, from this laptop | 3.5 s | 5.4 s |

3 of the 10 were refused (the same kind of refusals the Week 5 evaluation shows). **p95 is above the 4 s target** in `capstone-architecture.md`. One run of 10, so the p95 is essentially the slowest request; it is a signal, not a measurement. Likely contributors (not isolated): the App Service (Central India) calls Azure OpenAI in South India; the answerability check and the answer are two sequential model calls; the free plan is a shared, small instance. The very first request after deployment took 9.9 s (client and token setup).

## What I found along the way

- **The free semantic-ranker allowance is used up.** The first local run of the API returned 502 with `Free Query Semantic Usage exceeded for the month`. My evaluation runs consumed it (I never confirmed the allowance's size, and I did not verify when it resets; the message says "for the month"). The service now has an opt-in fallback: `AzureHybridRetriever(..., semantic_fallback=True)` repeats a refused semantic query as plain hybrid search and counts it (`fallbacks`), only for that error. It is **off by default** so evaluations still fail loudly instead of scoring a different system, and **on in the API**. The fallback is visible in the log only. **The hosted assistant is therefore currently running with the weaker ranking** (on our questions, Azure hybrid alone had Hit@1 0.62 against 0.86 with the ranker), and the full `ask` pipeline's answer quality without the ranker was **not measured**. Until the allowance resets, the Azure evaluation scripts that use the ranker will fail.
- **A role ID written from memory was wrong.** "Key Vault Secrets Officer" has a different ID from the one I typed (`RoleDefinitionDoesNotExist`). Look IDs up (`az role definition list --name ...`) instead of recalling them.
- **A Key Vault reference stays unresolved until the app is restarted or redeployed.** It read `SecretNotFound` after I created the secret, and `Resolved` after the deployment that followed. Create the secret before the first start, or restart.
- **`az webapp deploy` is unreliable about reporting.** One run printed a failure with no cause; the next hung for over ten minutes while the server log showed "Deployment successful" two minutes in. I did not diagnose why. Check the server-side deployment log (`az webapp log deployment show`) and the site itself, not only the command's exit.
- **A CI-simulation caught a test of mine that would have failed CI:** it imported the Azure SDK before its `importorskip` guard.

## Not done and open

- [ ] **Azure ML** (workspace, compute, jobs, model registry, a managed endpoint). Findings so far: the `az ml` extension is not installed; quota is 4 vCPUs in each of several VM families in Central India; **the Week 3 model was never saved** (only scripts that train it), so serving it means training, saving and registering a model and writing a scoring script. A managed online endpoint bills for its instance for as long as it exists.
- [ ] Book the AI-102 exam date (yours).
- [ ] Re-measure latency and ranking quality after the semantic allowance resets; try B1 (always-on, more CPU) for the p95.
- [ ] Decide whether to keep the hosted app. The free plan and the vault cost almost nothing; the app is publicly reachable but needs the key for `/ask`.
- [ ] Not tested: the F1 plan's daily CPU-time limit (what happens when it is reached), the global rate limit on the hosted app, and the whole `rg-payments-rag-w8` group being deleted (the app's roles on the OpenAI account and the search service are in another group and are expected to remain as orphans, as in Week 7).
- [ ] Week 9: the Dockerfile and the CI/CD pipeline that deploys on merge (today's deployment is a manual zip deploy).
