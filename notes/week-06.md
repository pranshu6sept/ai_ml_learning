# Week 6: orchestration

Roadmap items: LangGraph (state, nodes, conditional edges, retries, human in the loop); tool calling and structured outputs with Pydantic; a light Semantic Kernel pass; **deliverable: the capstone graph route -> retrieve -> grade -> generate -> validate.** Concepts are explained in `week-06-fundamentals.md`.

## What was built

| Item | Where |
|---|---|
| Typed model outputs (`Route`, `QueryRewrite`, `CitedAnswer`), strict JSON schema, validated again with Pydantic | `payments_rag/structured.py`; `AzureChatGenerator.complete_structured` |
| The graph: state, nodes as plain functions, wiring, retries, human review | `payments_rag/graph/` (`nodes.py`, `build.py`) |
| Tool calling: the model proposes `search_corpus` arguments (query, regions, date limits); we validate them and build a `SearchFilter` | `payments_rag/tools.py`; `AzureChatGenerator.plan_search`; optional `plan_filters=True` |
| Run it | `uv run --project capstone --all-groups python -m payments_rag.ask "question" --graph` (add `--review` to be asked when the evidence is partial) |
| Graph evaluation vs the Week 5 pipeline, on the 95 golden questions | `evals/run_graph.py` -> `results/graph.md` (v2) and `results/graph_v1.md` |
| Tool-argument accuracy and filter damage | `evals/run_tool_planning.py`, `evals/planning_questions.json` -> `results/tool_planning.md` |
| Semantic Kernel sample (plugin + automatic function calling + a filter) | `capstone/examples/semantic_kernel_sample.py`, run in a throwaway environment |

Dependencies: `langgraph` is an optional group (`uv sync --group orchestration`); `pydantic` is now a main dependency. The graph's node logic has no LangGraph import, so most graph tests also run in CI; the wiring tests skip when LangGraph is absent.

The graph, as built:

```
route -> retrieve -> grade -> generate -> validate -> done
   |         ^         |                      |
   |         +-rewrite-+ (once)              +-> generate again (once) -> repair or refuse
   +-> decline (out of scope) / small talk         (optional: grade partial -> human review)
```

## Graph evaluation: the honest result

Same 95 golden questions, same retrieval (Azure hybrid + semantic ranker), same answering model, same judge (gpt-4.1-mini, so scores are optimistic). One run each.

| Measure | Plain `ask` (Week 5) | Graph v1 | Graph v2 |
|---|---|---|---|
| Answerable questions answered | 57 of 69 | 52 | 57 |
| False refusals | 12 | 17 | 12 |
| Faithfulness (answered) | 0.99 | 0.95 | 0.99 |
| Correctness vs reference (answered) | 0.96 | 0.99 | 0.94 |
| Correctness end to end | 0.80 | 0.75 | 0.78 |
| Unanswerable correctly refused | 25 of 26 | 24 | 24 |
| Latency median / p95 (s) | 2.7 / 4.3 | 4.4 / 6.2 | 4.5 / 7.7 |
| Model calls per question (judge excluded) | not recorded | 3.3 | 3.4 |

**Summary: the graph does not beat the plain pipeline on these measures.** After the fixes below it is level on answers and faithfulness, slightly lower on correctness, slower, and it refuses 24 rather than 25 of the 26 unanswerable questions. What it adds is control, not accuracy.

**Version 1 was worse, and why.** All 12 of the plain pipeline's false refusals were repeated, plus five more, each from a new part: four answers (q12, q15, h06, n02) failed my one-uncited-sentence validation twice and were refused, and the router declined q20 ("Which bank looks after the shop's account?") as out of scope. Faithfulness fell to 0.95 because answers elaborated beyond the passages ("enhance security", "implying that...").

**Version 2 fixes, made after seeing those results** (so v2's numbers on the dev questions are partly tuned to them):
1. On the last attempt, if the only problem is uncited sentences, drop them and keep the rest instead of refusing.
2. The router prompt now says everyday wording about shops, merchants, cards and banks is in scope.
3. The generation prompt now says to state only what the passages say.

**What each added step actually did in v2:**

| Step | Result |
|---|---|
| Router | Declined 5 questions, all 5 unanswerable, so it saved a search and a grade for each; it declined no answerable question after fix 2 |
| Search rewrite | 34 rewrites; rescued one answerable question that the plain pipeline had refused (h02). Net effect about zero: i07 (answered by the plain pipeline) was refused, and the unanswerable a04 was answered. Low value for about 2 extra model calls each |
| Validation + regeneration | 7 first drafts failed; every one was regenerated once |
| Repair (drop uncited sentences) | Fired on 7 answers. On multi-part questions it removes content: q23 and i04 (the steps of a card payment) are now judged `incorrect`, i02 and q12 `partial`. For those, a refusal would arguably be better than a partial answer |

By question set (v2, answerable): dev 34 of 43 answered, correct end to end 0.76; held-out 12 of 12, 0.96; corpus_update 5 of 5, 1.00; independent 6 of 9, 0.50. The plain pipeline's end-to-end figures were 0.77, 0.88, 0.90 and 0.78. Held-out is higher and independent lower, but the independent set is 9 questions: one question is 11 points.

Two unanswerable questions still got answers (nu1 and a04). a04 is a regression against the plain pipeline: the answer said the investigation "should be completed within 30 days", which the passage does not state.

## Tool calling: argument accuracy and filter damage

`results/tool_planning.md`; the model is forced to call `search_corpus`, the arguments are validated, and dates and regions are re-checked in code.

| Measure | Result |
|---|---|
| Regions exactly as expected (18 questions I labelled before running) | 18 of 18 |
| Date limit set exactly when expected | 18 of 18 |
| Golden answerable questions where the model set any filter | 22 of 69 |
| Golden questions where the filter would exclude every gold document | 0 of 69 |

Read with care: the labelled set is mine and easy (perfect scores say it cannot tell a strong planner from a weak one), the damage check is computed from the registry and not from a search, and **the retrieval benefit of filtering was not measured**. The graph drops the model's filters on the rewrite retry as a safeguard; that safeguard is tested but not needed on this data.

## Semantic Kernel (light pass)

The sample registers the corpus search as a plugin, lets the model decide which functions to call (automatic function calling, which replaced SK's planners), and logs each call with a filter. In two live runs the model called `search_corpus` for a definition question and chose the document list plus a search for a broader one. It has no refusal check or validation and was not evaluated: its answer to "What is remittance information?" adds a sentence about "improving data quality" that I did not check against the passages.

## Operational findings

- **Rate limits look like slowness.** The chat deployment's request limit is 50 per minute (I paced for 150 at first). Single calls took about 6 s while an evaluation ran against 0.4 to 1.1 s on a quiet deployment, and a second process got a 429. I believe silent SDK retries explain it but did not log them. Latency numbers above were measured at 30 requests per minute, excluding pacing waits.
- **Capacity raised.** The chat deployment went from 10K to 50K tokens per minute (live, and `main.bicep` updated). Capacity caps speed, not cost.
- **Environment.** `azure-ai-evaluation` and `semantic-kernel` are run in throwaway environments, not added to the project.

## Checklist

- [x] LangGraph: state, nodes, conditional edges, bounded retries, human in the loop (tested with a scripted model)
- [x] Tool calling and structured outputs with Pydantic
- [x] Light Semantic Kernel pass: one small sample
- [x] Deliverable: graph route -> retrieve -> grade -> generate -> validate, run on the golden set with an evaluation table
- [x] Write-up
- [ ] Decide whether the search rewrite is worth keeping (1 rescue in 34)
- [ ] Revisit the repair step for multi-part answers (refuse, or regenerate, instead of dropping steps)
- [ ] Measure whether filter planning improves retrieval, not only argument accuracy
- [ ] Latency: re-measure p95 on a quiet deployment, and consider running route and retrieve in parallel
- [ ] Durable checkpointer (the demo uses in-memory)
