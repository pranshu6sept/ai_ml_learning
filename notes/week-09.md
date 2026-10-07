# Week 9: CI/CD and eval gates (in progress)

Roadmap items: multi-stage Dockerfile; GitHub Actions lint → test → eval gate → build → deploy; experiment tracking; prompts versioned in Git with a golden-set gate; **deliverable: a green pipeline that deploys on merge to main.**

## Status against the roadmap

| Item | Status |
|---|---|
| Multi-stage Dockerfile | **Done** (`capstone/Dockerfile`), built and smoke-tested |
| CI builds the image and smoke-tests it | **Done** (`image` job in `.github/workflows/ci.yml`) |
| Eval gate (golden-set scores below threshold fail CI) | Not started |
| Deploy on merge to main | **Written, not yet run**: `deploy` job in CI, container hosting in `infra/week8.bicep` (below) |
| Experiment tracking | Partly: the Week 8 Azure ML training job logs parameters and metrics to MLflow |

## The image (`capstone/Dockerfile`)

Three stages: `web` (Node 22) builds the React page; `deps` installs `deploy/requirements.txt` (the same pinned list App Service uses) into a virtualenv; `app` copies the virtualenv, `payments_rag/` and the built page onto `python:3.11-slim`. The final image has no Node, no build cache and no tests, runs as a non-root user (`app`, uid 10001), and has a `HEALTHCHECK` on `/health`. `.dockerignore` keeps `.env` files, `node_modules`, tests, evals and docs out of the build context.

Measured (one local build):
- the container starts, `/health` returns `{"status":"ok","configured":false}` (no Azure settings given), `/` serves the page with the CSP header, `POST /ask` without the key returns 401, Docker reports the container `healthy`;
- **image size 696 MB**, mostly the virtualenv (382 MB), of which SciPy 113 MB, scikit-learn 51 MB, NumPy 45 MB (+58 MB of their bundled libraries). They come from the retrieval code's dependencies; dropping them would mean changing the pipeline, not the Dockerfile.

The container cannot use `az login`, so for real answers it needs a managed identity (in Azure) or the identity's settings passed in. The smoke test needs neither.

## Deploy on merge

Decision (yours): run the Docker image rather than the zip, from a Basic Azure Container Registry (about 5 USD a month, covered by the free credit for now). Sign-in from GitHub is OIDC, so no Azure secret is stored in GitHub.

- `infra/week8.bicep` gained `hosting = 'container'` (default still `zip`): the registry (admin user off), `AcrPull` for the app's identity, and `payrag-github-deployer`, a user-assigned identity with a federated credential for `repo:pranshu6sept/ai_ml_learning:ref:refs/heads/main`, holding `AcrPush` on the registry and Website Contributor on the app only.
- The `deploy` job (`.github/workflows/ci.yml`) runs after `check`, `frontend` and `image` pass, only for `main` (push or a manual run), and is skipped until the repository variables exist. It pushes the image tagged with the commit SHA, sets the app's image, and fails unless `/health` reports `configured: true` within 5 minutes.
- Checked here: the template compiles and lints clean with the Bicep CLI (0.48.1), and the workflow passes actionlint. **Not checked: nothing has been deployed.** Unverified until the first run: that the free F1 plan runs this container (image 696 MB), and the three role definition IDs, which I wrote from memory (check with `az role definition list --name AcrPull --query [0].name`, likewise `AcrPush` and `Website Contributor`; Week 8 had a wrong ID).
- Steps: `infra/README.md`, "Week 9".

## Open

- [ ] **First deploy**: deploy the template with container hosting, set the six repository variables, run CI on `main` by hand, record the result (time to healthy, a real `/ask`).
- [ ] Eval gate: which golden-set metrics, which thresholds, and how to run them in CI without paying for model calls on every push.
