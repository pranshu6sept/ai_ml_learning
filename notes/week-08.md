# Week 8: hosting and identity

Roadmap items: Azure ML (workspace, compute, jobs, model registry, a managed endpoint that serves the Week 3 model); deploy the capstone API to App Service or Functions; Key Vault and managed identity with no keys in code or env files; **deliverable: the capstone reachable at a public URL, keyless auth to Azure services.**

This file records what is done and measured. The Azure ML part is described in its own section below.

## Status against the roadmap

| Item | Status |
|---|---|
| Deploy the capstone API to App Service | **Done**: FastAPI app on a Linux App Service (free F1 plan), public HTTPS URL |
| Key Vault and managed identity, no keys in code or env files | **Done and audited** (below) |
| Deliverable: public URL with keyless auth to Azure services | **Done**, with the limits listed below |
| A React front end for the API (added at your request) | **Done**, served by the API at the same URL (below) |
| Azure ML: workspace, compute, jobs, registry, managed endpoint for the Week 3 model | **Done**: trained as a job, registered (v2), served by a managed endpoint, tested, then deleted (below) |
| Book the AI-102 exam date | **Removed from the plan**: AI-102 is retired (replaced by AI-103) and the exam is not needed for the capstone |

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

## The React front end (`capstone/frontend/`)

A Vite + React + TypeScript page: key field, question box (Enter sends, 1000-character counter), one-click example questions, a service-status pill, cited answers with numbered badges that jump to the sources list, an amber refusal card with the reason, thumbs up and down, and a history of this session's answers. Light and dark themes, usable at phone width. How to run it is in `capstone/frontend/README.md`.

**One origin, no CORS.** The API serves the built files at `/` (from `payments_rag/web/` in the deployment zip), so the page and the API share one address. In development the Vite server proxies the API paths instead. `build_zip.py` includes the built page and **fails if it is missing** (or takes `--api-only`), so a deployment cannot silently ship without its page.

**The key.** Anything in a web page is public, so the API key is typed into the page, kept in `sessionStorage` (this tab only, cleared when it closes), sent as `X-API-Key`, and never written to `localStorage` or the build. It is a shared secret that stops strangers spending money on the model; it is not user accounts.

**Safety choices**, each with a test: answers render as text and React elements, never HTML (a hostile `<img onerror>` answer shows as literal text); only `https` source addresses become links, with `rel="noopener noreferrer"`; error messages are fixed text (a server's error detail is never shown); the server sends a strict Content-Security-Policy (own scripts, styles and connections only, no framing, no inline script or style), `nosniff`, `no-referrer` and `X-Frame-Options: DENY`, except on `/docs`, which loads its interface from a CDN.

**Tests and checks.**
- 43 front-end tests (Vitest + Testing Library) cover the API client's error mapping (401, 422, 429 with `Retry-After`, 5xx, network, abort), the citation and source parsing, and the page: answers, refusals, errors, the countdown after a 429, Enter versus Shift+Enter, the length limit, the key's storage, feedback, history and the hostile-answer case. 9 more backend tests cover serving the page, headers and the unshadowed API.
- A real-Chrome run (Playwright, throwaway environment) against the local server and then the **hosted URL**: the wrong key shows the right message; a real question returned a cited answer with 3 sources and 4 citation badges; a refusal showed as one; feedback was accepted; the key sat in `sessionStorage` and not `localStorage`; the phone layout (390 px, dark mode) had no horizontal overflow; the console showed no errors and no CSP violations apart from the 401 I caused on purpose.
- CI has a new `frontend` job (`npm ci`, typecheck, tests, build). I ran those steps from a clean install locally but **could not run GitHub Actions itself**, so its first real run is on your next push.

**What it found.** The real-browser run caught two things unit tests did not: the browser requests `/favicon.ico` on every visit and got a 404 (fixed with an inline icon), and my first run failed because I had started the server from the wrong folder so it could not find `.env` (the page correctly showed the error). A unit test also caught a real bug: a source whose location contained parentheses (a Wikipedia-style URL, or `javascript:alert(1)`) was silently dropped, so its citation looked missing; the parser now splits on the last ` (`.

**Not done.** No accessibility audit beyond labels, roles and keyboard use (no screen-reader or automated axe run); no end-to-end test in CI (the browser run was manual); history is in memory only, so a reload clears it; the page does not stream the answer (the API is not streaming, so an answer appears after 2 to 5 s).

## Azure ML (`classical_ml/azureml/`, `infra/week8-ml.bicep`)

Workspace `payrag-ml-udonru` and a CPU cluster that scales to zero. `train.py` retrains the Week 3 LightGBM model as a job (stratified hold-out, same hyperparameters; native Booster so serving returns a probability) and saves it as an MLflow model; metrics from the cloud run matched the local run. Registered as `fraud-lightgbm` v2 (v1 lacks a serving dependency and must not be deployed).

**Endpoint test:** `payrag-fraud` / `blue` (Standard_DS2_v2 x1) scored `sample-request.json` as **0.954** for the fraud row and **0.00008** for the normal row. Two rows only, so this shows the endpoint works, not that the model is good. The endpoint was **deleted straight after**; no endpoint or VM remains. The workspace, registry and cluster are still there (the registry and storage cost a little; delete `rg-payments-rag-w8ml` when finished).

**Failed attempts before it worked:**
- The second deployment (v2) failed in the image build: pip got `ReadTimeoutError` from pypi and "No matching distribution found for azureml-inference-server-http". The same config succeeded on a retry, so I treat it as a transient network failure, not proven.
- A failed deployment may still bill, so I deleted the endpoint each time and checked the list was empty.
- Setup pitfalls: the workspace Key Vault must use access policies; extra resource providers had to be registered; the base image `openmpi4.1.2-ubuntu20.04` no longer exists (used a curated environment).

## What I found along the way

- **The free semantic-ranker allowance is used up.** The first local run of the API returned 502 with `Free Query Semantic Usage exceeded for the month`. My evaluation runs consumed it (I never confirmed the allowance's size, and I did not verify when it resets; the message says "for the month"). The service now has an opt-in fallback: `AzureHybridRetriever(..., semantic_fallback=True)` repeats a refused semantic query as plain hybrid search and counts it (`fallbacks`), only for that error. It is **off by default** so evaluations still fail loudly instead of scoring a different system, and **on in the API**. The fallback is visible in the log only. **The hosted assistant is therefore currently running with the weaker ranking** (on our questions, Azure hybrid alone had Hit@1 0.62 against 0.86 with the ranker), and the full `ask` pipeline's answer quality without the ranker was **not measured**. Until the allowance resets, the Azure evaluation scripts that use the ranker will fail.
- **A role ID written from memory was wrong.** "Key Vault Secrets Officer" has a different ID from the one I typed (`RoleDefinitionDoesNotExist`). Look IDs up (`az role definition list --name ...`) instead of recalling them.
- **A Key Vault reference stays unresolved until the app is restarted or redeployed.** It read `SecretNotFound` after I created the secret, and `Resolved` after the deployment that followed. Create the secret before the first start, or restart.
- **`az webapp deploy` is unreliable about reporting.** One run printed a failure with no cause; the next hung for over ten minutes while the server log showed "Deployment successful" two minutes in. I did not diagnose why. Check the server-side deployment log (`az webapp log deployment show`) and the site itself, not only the command's exit.
- **The first managed-endpoint deployment crash-looped and never served a request.** The scoring script Azure ML generates for an MLflow model imports `azureml.ai.monitoring` (line 20), but the serving environment is built only from the model's own conda file, which MLflow wrote without that package. Each worker died with `ModuleNotFoundError: No module named 'azureml'` (gunicorn exit code 3) and restarted until the deployment timed out. I deleted the endpoint (about six minutes; no endpoint or VM left) and made `train.py` save the model with `extra_pip_requirements=["azureml-ai-monitoring"]`. Model version 1 lacks the package and must not be deployed again; `deployment.yml` now points at version 2. Before paying for an instance, check the registered model's `requirements.txt` lists the package.
- **A CI-simulation caught a test of mine that would have failed CI:** it imported the Azure SDK before its `importorskip` guard.

## Not done and open

- [x] Azure ML: done (above). Not tested: scaling, authentication rotation, latency of the endpoint, monitoring.
- [ ] Re-measure latency and ranking quality after the semantic allowance resets; try B1 (always-on, more CPU) for the p95.
- [ ] Decide whether to keep the hosted app. The free plan and the vault cost almost nothing; the app is publicly reachable but needs the key for `/ask`.
- [ ] Not tested: the F1 plan's daily CPU-time limit (what happens when it is reached), the global rate limit on the hosted app, and the whole `rg-payments-rag-w8` group being deleted (the app's roles on the OpenAI account and the search service are in another group and are expected to remain as orphans, as in Week 7).
- [ ] Week 9: the Dockerfile and the CI/CD pipeline that deploys on merge (today's deployment is a manual zip deploy; it should build the front end first).
