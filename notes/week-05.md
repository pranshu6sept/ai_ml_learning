# Week 5: retrieval and answer evaluation

Roadmap items: golden set with reference answers; recall@k, MRR, nDCG; faithfulness and answer relevance; a table comparing the four chunking
strategies; `evals/` runnable with one command, results committed. Earlier groundwork is in `week-04.md`.

## What was built

| Item | Where |
|---|---|
| Golden set: 95 questions (69 answerable with expected source passages and a reference answer, 26 to refuse) | `capstone/evals/golden_set.jsonl`, built by `build_golden_set.py` from the question files and `golden_references.json` |
| recall@k and nDCG@k (tested functions) | `payments_rag/metrics.py`, wired into `evaluate()` in `evaluate_chunking.py` |
| Retrieval table: every chunking strategy x local retriever, per question set, optional Azure | `run_retrieval.py` -> `results/retrieval.md` |
| Answer quality: faithfulness, relevance, correctness vs reference, refusals, latency | `run_generation.py` -> `results/generation.md`; judge prompts and parsers in `payments_rag/answer_eval.py` (tested) |
| One command | `uv run --all-groups python capstone/evals/run_all.py` (offline) or `... run_all.py --azure` (adds Azure retrieval and the answer run) |

A test fails if `golden_set.jsonl` drifts from its source files. The reference answers are mine, written from the gold passages, so they
restate what the corpus says; where the corpus says little (for example UPI data protection), the reference says so.

## Retrieval results (all 69 answerable questions)

Best local setup: structure-aware chunks with hybrid search (BM25 with stemming + embeddings, reciprocal rank fusion).

| Hit@1 | Hit@3 | Recall@1 | Recall@3 | Recall@5 | MRR@10 | nDCG@3 | nDCG@5 |
|---|---|---|---|---|---|---|---|
| 0.52 | 0.84 | 0.50 | 0.83 | 0.94 | 0.70 | 0.68 | 0.73 |

- Recall@5 of 0.94 clears the 0.85 target in `capstone-architecture.md`, on my own questions. Recall@k is the share of a question's gold
  passages covered; Hit@k is satisfied by either of two acceptable passages, so Recall is the stricter of the two.
- Structure-aware chunks had the best nDCG@5 for all three retrievers (TF-IDF 0.63, BM25+stem 0.62, hybrid 0.73); semantic chunking was the
  worst for the two lexical retrievers. The full 12-row table and the per-set tables are in `results/retrieval.md`.
- By set (structure-aware, local hybrid): dev Hit@3 0.91, held-out 0.83, corpus_update 0.40 (5 questions), independent 0.78 (9 questions).
  The small sets move 11-20 points per question.

### Azure retrieval in the same table (structure-aware chunks, same 69 questions)

| Retriever | Hit@1 | Hit@3 | Recall@5 | MRR@10 | nDCG@5 |
|---|---|---|---|---|---|
| local hybrid (BM25+stem, embeddings) | 0.52 | 0.84 | 0.94 | 0.70 | 0.73 |
| Azure hybrid (keyword + vector) | 0.62 | 0.84 | 0.91 | 0.75 | 0.77 |
| Azure hybrid + semantic ranker | 0.86 | 0.99 | 0.97 | 0.92 | 0.91 |

- The semantic ranker is the clear gain: Hit@1 from 0.62 to 0.86, nDCG@5 from 0.77 to 0.91. Azure hybrid without it is about level with the
  free local hybrid on Hit@3 and Recall@5.
- On the 9 independent questions it reaches Hit@3 1.00 (Azure hybrid alone 0.67); the per-set tables are in `results/retrieval.md`. One question
  is worth 11 points there.
- This is one run. It uses the free tier's semantic-query allowance, whose monthly size I have not confirmed.

## Answer-quality results (real pipeline on Azure, 95 questions, one run)

Pipeline: Azure hybrid search + semantic ranker (top 3) -> quote-verified answerability check -> cited answer, or refusal. Judge: the same
gpt-4.1-mini deployment, so scores are optimistic.

| Measure | Value |
|---|---|
| Answerable questions answered | 57 of 69 (12 false refusals) |
| Faithfulness: share of claims supported (answered) | 0.99; 56 of 57 answers fully supported (target 0.9) |
| Answer relevance (answered) | 0.96 |
| Correctness vs reference (answered) | 0.96; 53 judged fully correct |
| Correctness end to end (a refusal counts as 0) | 0.80 |
| Unanswerable questions correctly refused | 25 of 26 |
| Latency per question, excluding rate-limit waits (median / p95) | 2.7 s / 4.3 s |

What this says, and does not say:

- **The trade-off is visible.** The answerability gate is strict: 12 of 69 answerable questions were refused because the checker judged the
  passages "partial" or "none" (for example q07 who handles disputes, q10 what the issuing bank does, q31 what PSD3 is). That buys 25 of 26
  correct refusals and 56 of 57 fully supported answers. Whether that is the right operating point depends on whether a wrong answer or a
  refusal costs more; this run does not choose for you.
- **Faithfulness is high, but the judge is the answering model.** The one flagged answer (h05) has a claim ("allow instant transfers") the
  judge could not find in the passages. The four answered-but-"partial" correctness cases (q29, q32, h06, n04) mostly omit a condition or part of
  the reference; read them in `results/generation.md` before trusting the judge's strictness either way.
- **One unanswerable question got an answer** (nu1, penalty for breaching the RBI directions: the answer gave the customer-compensation rule,
  which is related but is not a penalty).
- **Latency p95 of 4.3 s is just over the 4 s target.** It is a single run from a laptop, covers search, the answerability check and the answer
  (not the judge calls), excludes rate-limit pacing waits but may include 429 retry waits; OpenAI (South India) and Search (Central India) are in
  different regions. Cost per query was not measured.
- **Not done as the roadmap words it:** no RAGAS and no Azure AI Foundry evaluators (my own tested judge prompts instead). That makes the numbers
  harder to compare with others'; a Foundry run as a cross-check is a sensible follow-up.

## Judge cross-check: a model that did not write the answers

`run_judge_check.py` re-graded the same 58 answers (the 57 answered answerable questions plus the one unanswerable question that got an answer)
with `gpt-5-mini`, a different model from the writer `gpt-4.1-mini`, using the same prompts and the same retrieved passages. Both are OpenAI
models, so this is not independent of the vendor. Full report: `results/judge_check.md`.

| What was judged | Raw agreement | Cohen's kappa | gpt-4.1-mini | gpt-5-mini |
|---|---|---|---|---|
| Faithfulness: every claim supported? | 0.95 | -0.02 | 56 of 57 fully supported | 56 of 57 fully supported |
| Relevance: direct / partial / off topic | 0.93 | 0.47 | 53 direct, 4 partial | 54 direct, 3 partial |
| Correctness: correct / partial / incorrect | 0.91 | 0.51 | 53 correct, 4 partial | 52 correct, 5 partial |

(Counts are over the 57 answerable questions; agreement is over all 58.)

- **The headline numbers survive a different judge.** Mean faithfulness is 0.99 and 1.00, correctness 0.96 for both, relevance 0.96 and 0.97.
  Nothing was marked off-topic or incorrect by either judge.
- **Faithfulness kappa of -0.02 is an artefact, not a finding about quality.** Nearly every answer is "supported", and each judge flagged exactly
  one answer, a different one (h05 by gpt-4.1-mini, i04 by gpt-5-mini), so there is no agreement above chance on the rare class to measure.
  Read the raw 0.95 and the disagreement list instead. Relevance and correctness show moderate kappa (0.47 and 0.51): they agree on most
  answers and differ by one level on a few.
- **Each judge caught something the other missed.** gpt-5-mini flagged i04 ("there are four steps": a count the passages do not state) and,
  on the unanswerable nu1, the compensation claim; gpt-4.1-mini flagged h05 ("instant transfers"), which gpt-5-mini accepted. I have not
  adjudicated these by hand, so the true faithfulness of the 57 answers is "56 of 57 by either judge, but not the same one".
- **Both judges are lenient on the same kind of answer** (nothing below "partial"), so a human read of the 5 or so flagged answers would still
  be the real check.

## Foundry evaluators cross-check

`run_foundry_check.py` graded the same 58 answers with Azure AI Foundry's ready-made evaluators (`azure-ai-evaluation` 1.18.7), judge model
`gpt-5-mini`, scores 1 to 5, 3 or more passes. It runs in an isolated environment (`uv run --no-project --with azure-ai-evaluation ...`, command
in the script) because the package needs pandas below 3 and would downgrade this repo's pandas; it is not a project dependency. Report:
`results/foundry_check.md`. RAGAS was not run.

| Evaluator | Mean | Pass (3+) | Scored 5 | Scored below 4 |
|---|---|---|---|---|
| Groundedness | 5.00 | 58 of 58 | 58 | 0 |
| Relevance | 3.91 | 58 of 58 | 4 | 9 |
| Similarity to the reference answer | 4.89 | 57 of 57 | 52 | 1 |

- **Groundedness agrees with the headline but is blunt.** Every answer scored 5, including the three that one of my two judges flagged at claim
  level (h05, i04, nu1). So no judge found an ungrounded answer in bulk, and Foundry's whole-answer score cannot resolve the single unsupported
  claim that my claim-by-claim judge looks for.
- **Relevance does not separate good from weaker answers here.** Short, correct factual answers score 3 or 4 because the scale rewards
  comprehensiveness ("lacks deeper detail"). My answers judged `direct` average 3.92 on it and those judged `partial` 3.80. I would not use it
  as a gate on this corpus.
- **Similarity does track correctness.** Answers my judge called `correct` average 4.94; the 4 it called `partial` average 4.25 (n = 4). The lowest
  score is n04 (3.0), one of my partial cases (it omitted the risk-based-handling part); h06, q37, q23 and i04 scored 4.
- **What this adds up to.** Three graders (the answering model, a different model, and Foundry's evaluators) agree that none of the 57 answers
  is badly wrong or ungrounded, and they disagree about the one or two borderline answers. The checks cannot settle those; a human read can.
  All three judges are OpenAI models.

## Checklist

- [x] Golden set of 50-100 questions with expected source passages and reference answers (95 questions; references written by me)
- [x] Retrieval metrics: recall@k, MRR, nDCG
- [x] Generation metrics: faithfulness and answer relevance (own judge; not RAGAS/Foundry), plus correctness vs reference
- [x] Four chunking strategies compared in a table (`results/retrieval.md`)
- [x] `evals/` runnable with one command (`run_all.py`), results committed
- [x] A judge that is not the answering model (gpt-5-mini re-graded the same answers; see above)
- [x] Cross-check with Foundry evaluators (RAGAS not run)
- [ ] Read the borderline answers by hand (h05, i04, nu1, n04, q29, q32, h06) and decide the labels
- [x] Azure retrieval variants in one table with the local ones (`run_all.py --azure`; the 95-question answer step re-renders from its cache)
- [ ] Decide the operating point for refusals (12 false refusals vs 25 of 26 correct refusals)
- [ ] CI gate on these numbers (Week 9)
