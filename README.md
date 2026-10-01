# AI/ML Learning

A 12-week path to an Azure GenAI/ML Engineer role, built as code. Two tracks share this repo:

| Folder | What | Weeks |
|---|---|---|
| `classical_ml/` | Fraud / credit-default model: pipelines, imbalance handling, GBM + SHAP | 1–3 |
| `capstone/` | Payments knowledge assistant: RAG on Azure AI Search + Azure OpenAI, LangGraph, evals, guardrails, tracing | 4–12 |
| `infra/` | Bicep for the Azure resources | 7+ |
| `notes/` | Weekly write-ups | every week |

## Setup

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --all-groups          # create .venv with runtime + dev deps
uv run pre-commit install     # ruff, ruff-format, mypy on every commit
```

## Everyday commands

```bash
uv run pytest                 # tests
uv run ruff check . --fix     # lint
uv run ruff format .          # format
uv run mypy                   # type check (strict)
```

CI runs the same four checks on every push and pull request.

## Results

Headline metrics will land here as each phase ships (PR-AUC for the classical model; recall@5, groundedness, p95 latency and injection block rate for the capstone).
