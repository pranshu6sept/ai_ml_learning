# Week 9: CI/CD and eval gates (in progress)

Roadmap items: multi-stage Dockerfile; GitHub Actions lint → test → eval gate → build → deploy; experiment tracking; prompts versioned in Git with a golden-set gate; **deliverable: a green pipeline that deploys on merge to main.**

## Status against the roadmap

| Item | Status |
|---|---|
| Multi-stage Dockerfile | **Done** (`capstone/Dockerfile`), built and smoke-tested |
| CI builds the image and smoke-tests it | **Done** (`image` job in `.github/workflows/ci.yml`) |
| Eval gate (golden-set scores below threshold fail CI) | Not started |
| Deploy on merge to main | Not started: needs an Azure identity GitHub can use (see "Open") |
| Experiment tracking | Partly: the Week 8 Azure ML training job logs parameters and metrics to MLflow |

## The image (`capstone/Dockerfile`)

Three stages: `web` (Node 22) builds the React page; `deps` installs `deploy/requirements.txt` (the same pinned list App Service uses) into a virtualenv; `app` copies the virtualenv, `payments_rag/` and the built page onto `python:3.11-slim`. The final image has no Node, no build cache and no tests, runs as a non-root user (`app`, uid 10001), and has a `HEALTHCHECK` on `/health`. `.dockerignore` keeps `.env` files, `node_modules`, tests, evals and docs out of the build context.

Measured (one local build):
- the container starts, `/health` returns `{"status":"ok","configured":false}` (no Azure settings given), `/` serves the page with the CSP header, `POST /ask` without the key returns 401, Docker reports the container `healthy`;
- **image size 696 MB**, mostly the virtualenv (382 MB), of which SciPy 113 MB, scikit-learn 51 MB, NumPy 45 MB (+58 MB of their bundled libraries). They come from the retrieval code's dependencies; dropping them would mean changing the pipeline, not the Dockerfile.

The container cannot use `az login`, so for real answers it needs a managed identity (in Azure) or the identity's settings passed in. The smoke test needs neither.

## Open

- [ ] **Deploy on merge**: the workflow needs to sign in to Azure. The keyless way is a federated credential (OIDC) on an app registration or user-assigned identity, scoped to the App Service, with `AZURE_CLIENT_ID`, `AZURE_TENANT_ID` and `AZURE_SUBSCRIPTION_ID` as repository variables (no secret). Also decide: keep the zip deploy, or run this image (needs a container registry, which costs money, or GitHub's registry with a pull credential).
- [ ] Eval gate: which golden-set metrics, which thresholds, and how to run them in CI without paying for model calls on every push.
