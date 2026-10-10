# Week 9: CI/CD and eval gates (in progress)

Roadmap items: multi-stage Dockerfile; GitHub Actions lint → test → eval gate → build → deploy; MLflow or Azure ML experiment tracking; prompts versioned in Git, and pull requests that drop golden-set scores below a threshold fail CI; **deliverable: a green pipeline that deploys on merge to main.**

Built fresh on `main`. An earlier unmerged branch (`claude/great-carson-6kp0ng`) also holds Week 9 work (container registry, OIDC deploy); I did not use or merge it.

## Status against the roadmap

| Item | Status |
|---|---|
| Multi-stage Dockerfile | **Done and run**: built locally, started, smoke-tested (below). Its CI job has not run on GitHub yet |
| CI: lint → test → eval gate → build | **Done**: `check` job (lint, format, types, tests, eval gate) and a `docker` job (build, smoke test), plus `frontend` |
| CI: deploy | **Not done**: needs a container registry (about 5 USD a month on Basic) and an Azure sign-in from GitHub; see "Not done" |
| Experiment tracking | **Done**: evaluation results logged to MLflow, locally and in the Azure ML workspace |
| Prompts versioned in Git; a PR that drops scores fails CI | **Done, with limits** (below) |
| Deliverable: green pipeline that deploys on merge | **Not done** (no deploy step) |

## Prompts in files (`payments_rag/prompts/`)

The three production prompts (the answer prompt, the strict citation rule, the answerability check) moved out of Python strings into `answer.txt`, `strict_citation_rule.txt` and `answerability.txt`, so a prompt change is a plain text diff. `prompt_version()` is a 12-character hash of the names and contents of all prompt files (now `5aca1c24bba7`).

The move had to change nothing the model sees. I captured the old prompts' output for a fixed example (answer, strict, abstention, answerability) before moving them, and `test_prompts.py` holds those strings: the new code reproduces all four byte for byte. A second test guards a trap I hit: the strict rule ended with a trailing space, which the repo's pre-commit hook strips, so the file stores it without and the code adds the space back.

Not moved: the judge prompts in `answer_eval.py` (they grade the system rather than run in it), and the prompts of the LangGraph path.

## The eval gate (`capstone/evals/eval_gate.py`, thresholds in `gate.json`)

CI runs it after the tests. Two kinds of check, both free and deterministic:

1. **Retrieval, recomputed in CI.** The offline BM25 retriever over the golden set: Hit@3 must be at least 0.70 and MRR@10 at least 0.58. The recomputed values (0.7246, 0.6092) equal the Week 5 numbers exactly, so CI reproduces them. This catches a change to the corpus, the chunker or the retriever.
2. **Answer quality, read from committed results.** `results/generation_no_semantic.json` must have faithfulness at least 0.90, correctness of answered at least 0.90, end-to-end correctness at least 0.65 and at least 0.90 of unanswerable questions refused. It must also carry the **current prompt version**: edit a prompt without re-running `run_generation.py` and the gate fails with a message saying so. I checked this on the real script: a one-phrase edit to `answer.txt` made the gate exit 1 on the prompt-version check, and restoring the file made it pass.

The thresholds are the measured scores minus about two questions of slack. They are not a statistical bound; with 69 answerable questions one question moves a score by 0.014 and the model's answers vary between runs, so a gate this tight can flag noise. Lower a threshold only in a PR that says why.

**What the gate cannot do.** Checking answer quality means calling Azure OpenAI, so CI does not do it on every pull request. The gate checks that committed numbers are fresh for the current prompts and clear the bar. It cannot tell whether those numbers really came from this code: someone could commit edited results, and only a reviewer reading the results diff would see that. A real re-run in CI would need the GitHub-to-Azure sign-in described below. The with-ranker results (`generation.json`) are not gated: they predate the prompt hash, and the ranker's free allowance is used up, so I cannot reproduce them.

## Experiment tracking (`capstone/evals/track_results.py`)

Logs a results file as one MLflow run: parameters (prompt version, git commit with `+dirty` when the tree has uncommitted changes, whether the ranker was on, question count), every number in the summary as a metric, and the JSON and Markdown report as artifacts. It needs no model call.

- **Local:** a SQLite file `mlflow.db` in the repo root (git-ignored). MLflow 3 moved its plain-folder store to maintenance mode and raises an error for it, which I found by running it; the opt-in `tracking` dependency group therefore includes `sqlalchemy` and `alembic`.
- **Azure ML:** set `MLFLOW_TRACKING_URI` to the workspace's URI (`az ml workspace show --query mlflow_tracking_uri -o tsv`) and add `azureml-mlflow`; `az login` is enough, no key. I logged the no-ranker evaluation there (experiment `payments-rag-eval`).
- **Found by running it:** my first Azure ML attempt crashed printing MLflow's emoji to the Windows console (fixed with a UTF-8 stdout) and left a half-finished duplicate run in `RUNNING`. Asking MLflow to delete it had no visible effect (it stayed in the list as `RUNNING`), so I ended it as `FAILED`; it is still listed beside the good run (`94902dac`).
- The logging test only runs where `mlflow` is installed, so CI (which does not install it) skips it; the parameter and metric mapping is tested everywhere.

## The Dockerfile (`capstone/Dockerfile`)

Three stages: `web` builds the React page, `deps` installs the compiled requirements (`deploy/requirements.txt`, no torch) into a virtualenv, and `runtime` is `python:3.11-slim` plus the virtualenv, the package and the built page. No Node, compiler or pip cache in the final image, a non-root user (uid 10001), a healthcheck, and no `.env` or key built in.

Built and run locally (Docker 28.1.1): the image is **492 MB**. In a container started without any Azure settings: `/health` returned `{"status":"ok","configured":false}`; `/` served the page with its Content-Security-Policy; `/ask` returned 401 without a key and with a wrong key; the process ran as `app`; no `.env` files were in the image; the Docker healthcheck reported healthy; and the prompt version inside the container matched the one on disk. **Not tested:** a real question through the container (it needs Azure sign-in, which a plain container does not have), the base images' security patch level (tags are not pinned to digests), and a build on a machine other than this laptop.

## CI

`check` (ruff, format, mypy, tests, eval gate), `docker` (build, smoke test: `/health`, the page, 401 without the key, non-root) and `frontend`. I ran every `check` step in a fresh environment built the way CI builds it (`uv sync --group api`, Python 3.11): all passed. The `docker` job is a copy of the commands I ran locally, but **it has not run on GitHub**; its first real run is on your next push.

## Not done and open

- [ ] **Deploy on merge.** Needs: (1) a container registry (Basic is about 5 USD a month; the zip deploy today needs none); (2) a user-assigned identity with a federated credential so GitHub signs in to Azure without a stored secret; (3) changing the hosted app from zip to container, which takes it down until the first image is pushed. All three change the live app and your Azure account, so I have not started them without your go-ahead. The earlier unmerged branch has a template for this that I have not reviewed or tested.
- [ ] Run the evaluation inside CI on prompt changes (needs the same Azure sign-in, plus model cost per run and rate-limit pacing).
- [ ] Pin the Docker base images by digest; scan the image for vulnerabilities.
- [ ] Gate the with-ranker results once the free allowance resets and they can be re-run with a prompt hash.
