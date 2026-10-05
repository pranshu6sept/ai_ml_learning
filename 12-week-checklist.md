# 12-Week Plan: Azure GenAI/ML Engineer — Tracker

Start: **Mon 2026-10-05** · End: **Sun 2026-12-27** · ~10–12 hrs/week
Tick boxes as you go (`[x]`). Every week ends with something pushed to GitHub and a short "what I learned" note.

**Weekly rhythm:** 2h theory · 5–6h building · 1h write-up · 1–2h interview Q&A

---

## Week 0 (before 2026-10-05): setup
- [ ] Repo skeleton pushed (see `capstone-architecture.md` → Repo structure)
- [ ] Python 3.11+, `uv` or `poetry`, pre-commit with ruff + mypy, pytest wired up
- [ ] GitHub Actions: lint + test on every push
- [ ] Azure free account / credits activated; set a budget alert (e.g. $50/month)
- [ ] `notes/` folder for weekly write-ups

---

## Phase 1: ML fundamentals + Python rigor

### Week 1 · Oct 5–11 · pandas, NumPy, sklearn pipelines
- [ ] pandas/NumPy refresher on a tabular dataset
- [ ] Supervised vs unsupervised (one example each)
- [ ] Train/val/test split and k-fold CV; explain leakage
- [ ] `sklearn.Pipeline` + `ColumnTransformer`
- [ ] **Deliverable:** notebook → refactored into `classical_ml/` package with tests
- [ ] Write-up + push

### Week 2 · Oct 12–18 · Metrics, imbalance, overfitting
- [ ] Pick dataset (e.g. Kaggle credit-card fraud, or Home Credit / Taiwan credit default)
- [ ] Precision/recall/F1, ROC-AUC vs PR-AUC (and when PR-AUC matters)
- [ ] Imbalance: class weights vs SMOTE vs threshold tuning, compared with numbers
- [ ] Regularization (L1/L2), early stopping
- [ ] Feature engineering pass
- [ ] **Deliverable:** fraud/credit-default model with a metrics table
- [ ] Write-up + push

### Week 3 · Oct 19–25 · GBMs, SHAP, PyTorch basics
- [ ] XGBoost or LightGBM beats the Week 2 baseline (record delta)
- [ ] SHAP global + local explanations
- [ ] PyTorch: tensors, autograd, training loop, one small NN on the same data
- [ ] **Deliverable:** write-up "why a GBM beats an LLM for this problem" (cost, latency, explainability, data shape)
- [ ] Write-up + push

**Phase 1 exit check:** tested package, CI green, one metrics table, one SHAP plot.

---

## Phase 2: RAG + orchestration

### Week 4 · Oct 26–Nov 1 · RAG core
- [ ] Assemble the banking/payments corpus (public docs: e.g. ISO 20022 guides, card-scheme rules summaries, RBI/PSD2/PCI-DSS public docs, your own written FAQs). No confidential employer material.
- [ ] Chunking: fixed, recursive, semantic, structure-aware (implement all four)
- [ ] Embeddings model choice; vector DB concepts (HNSW, filters)
- [ ] Azure AI Search index with vector + keyword (hybrid) + semantic ranker
- [ ] **Deliverable:** `ingest` + `retrieve` working end to end against AI Search
- [ ] Resume: start reframing (see Resume section)
- [ ] Write-up + push

### Week 5 · Nov 2–8 · Retrieval + answer evaluation
- [ ] Golden set: 50–100 questions with expected source chunks and reference answers
- [ ] Retrieval metrics: recall@k, MRR, nDCG
- [ ] Generation metrics: faithfulness/groundedness, answer relevance (RAGAS or Azure AI Foundry evaluators)
- [ ] Compare the 4 chunking strategies with a results table
- [ ] **Deliverable:** `evals/` runnable with one command, results committed
- [ ] Write-up + push

### Week 6 · Nov 9–15 · Orchestration
- [ ] LangGraph: state, nodes, conditional edges, retries, human-in-the-loop
- [ ] Tool calling + structured outputs (Pydantic)
- [ ] Light Semantic Kernel pass (plugins, planners): one small sample
- [ ] **Deliverable:** capstone graph: route → retrieve → grade → generate → validate
- [ ] Write-up + push

**Phase 2 exit check:** graph answers golden-set questions with citations; eval table exists.

---

## Phase 3: Azure stack

### Week 7 · Nov 16–22 · Azure OpenAI, AI Foundry, AI Search deep dive
- [ ] Azure OpenAI: deployments, quotas/TPM, content filters, embeddings deployment
- [x] AI Foundry: project, ~~prompt flow~~ (skipped on purpose: retired 2027-04-20 and hub-projects only; see `notes/week-07.md`), evaluations, model catalog
- [ ] AI Search: indexers, skillsets, semantic ranker, vector profiles
- [ ] **Deliverable:** infra as code (Bicep or Terraform) for these resources
- [ ] Write-up + push

### Week 8 · Nov 23–29 · Azure ML, hosting, identity
- [ ] Azure ML: workspace, compute, jobs, model registry, managed endpoint (deploy the Week 3 model)
- [ ] Deploy capstone API to App Service (or Functions)
- [ ] Key Vault + managed identity; no keys in code or env files
- [ ] Book AI-102 exam date (DP-100 optional)
- [ ] **Deliverable:** capstone reachable at a public URL, keyless auth to Azure services
- [ ] Write-up + push

---

## Phase 4: MLOps/LLMOps + guardrails

### Week 9 · Nov 30–Dec 6 · CI/CD and eval gates
- [ ] Multi-stage Dockerfile
- [ ] GitHub Actions: lint → test → eval gate → build → deploy
- [ ] MLflow or Azure ML experiment tracking
- [ ] Prompts versioned in Git; PRs that drop golden-set scores below threshold fail CI
- [ ] **Deliverable:** green pipeline that deploys on merge to main
- [ ] Write-up + push

### Week 10 · Dec 7–13 · Guardrails
- [ ] Azure AI Content Safety: Prompt Shields, groundedness detection
- [ ] Input/output validators (Pydantic; Guardrails AI or NeMo Guardrails)
- [ ] PII redaction (account numbers, card PANs, IBANs)
- [ ] Adversarial set mapped to OWASP LLM Top 10 (injection, jailbreak, data leakage)
- [ ] Refusal + fallback behavior
- [ ] **Deliverable:** guardrail test report with block rates and false-positive rate
- [ ] Write-up + push

---

## Phase 5: Observability + polish

### Week 11 · Dec 14–20 · Observability and drift
- [ ] OpenTelemetry → Application Insights: span per LLM call (latency, tokens, cost, retrieval hits)
- [ ] Dashboard + alerts (p95 latency, error rate, cost/day, groundedness)
- [ ] User feedback capture (thumbs up/down stored with trace id)
- [ ] Drift: query/embedding distribution shift, retrieval-quality decay; PSI/KS for the classical model
- [ ] **Deliverable:** live App Insights dashboard (screenshot in README)
- [ ] Write-up + push

### Week 12 · Dec 21–27 · Polish
- [ ] README: architecture diagram, eval results, cost/latency numbers, failure analysis
- [ ] 3–5 minute demo video
- [ ] Final resume pass
- [ ] Write-up + push

---

## Resume and positioning (from Week 4)
- [ ] Reframe banking/payments work as "high-reliability, compliance-sensitive production systems"
- [ ] Any existing LLM/RAG work first, with real numbers
- [ ] Projects section led by the capstone with metrics (recall@5, groundedness, p95 latency, injection block rate)
- [ ] Summary leads with Azure + RAG + evals + guardrails
- [ ] Honest timeline story ready (no "2 years GenAI production" unless true)

## Interview prep (1–2 hrs/week; tick when you can answer out loud in 3 minutes)
- [ ] Classical ML vs LLM decision framework
- [ ] Design a RAG system end to end and justify each choice
- [ ] How you evaluate and regression-test an LLM app
- [ ] Prompt-injection threat model and mitigations
- [ ] Cost/latency optimization (caching, smaller models, batching, streaming)
- [ ] Drift monitoring for LLM and classical models
- [ ] Capstone trade-offs and failures walkthrough

## Success criteria by Week 12
- [ ] Capstone deployed on Azure with CI/CD
- [ ] Eval suite with recorded numbers, gated in CI
- [ ] Guardrail test report
- [ ] Live App Insights dashboard
- [ ] Classical-ML project with metrics and imbalance handling
- [ ] AI-102 passed or scheduled

## Weekly log
| Week | Shipped (link) | Key number | Hours | Notes |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |
| 4 | | | | |
| 5 | | | | |
| 6 | | | | |
| 7 | | | | |
| 8 | | | | |
| 9 | | | | |
| 10 | | | | |
| 11 | | | | |
| 12 | | | | |
