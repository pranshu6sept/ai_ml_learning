# Week 5 fundamentals: how to tell whether a RAG system is any good

Numbers come from `capstone/evals/` (golden set of 95 questions over the public payments corpus). Results are in `week-05.md`; this file explains the ideas behind them.

Contents: 1. Why evaluate in pieces · 2. The golden set · 3. Retrieval metrics · 4. Worked examples · 5. Answer metrics · 6. LLM judges and their biases · 7. Refusals · 8. Noise and honesty · 9. Latency and cost · 10. Tools: RAGAS and Foundry · 11. Interview check

---

## 1. Why evaluate in pieces

A RAG answer can be wrong for three different reasons, and each needs a different fix:

| Failure | What it looks like | Which metric shows it | Typical fix |
|---|---|---|---|
| The right passage was never found | confident answer from the wrong text, or a refusal | recall@k, MRR, nDCG | chunking, search method, reranker |
| The right passage was found but the answer ignores or adds to it | fluent answer with claims the passages do not support | faithfulness (groundedness) | prompt, citation rules, smaller scope |
| The answer is supported but does not answer the question | on-topic but beside the point | answer relevance, correctness | prompt, how many passages are passed |

If you only grade the final answer, you cannot tell which row you are in. So retrieval is scored on its own (no language model involved), then answers are scored on top.

---

## 2. The golden set

A **golden set** is a fixed list of questions, each with what a correct system must do:

- the **question**;
- the **expected source** (where the answer lives);
- a **reference answer** (what a correct answer says);
- or, for questions the corpus cannot answer, the expected behaviour: **refuse**.

Design choices in this repo:

- **Gold passages are phrases, not chunk ids.** A gold entry names a document and a phrase that must appear in a retrieved chunk. Chunk ids change whenever you change the chunker, so id-based gold would make the four chunking strategies impossible to compare fairly. A phrase works for every strategy.
- **Several acceptable passages.** Some questions are answered in two places (an overview and the FAQ). Hit@k accepts either; recall@k asks how many were found.
- **Unanswerable questions are part of the set** (26 of 95). A system that answers everything would score perfectly on the other 69 and still be dangerous.
- **Question sets with different trust levels.** `dev` questions were used while building the pipeline, so they flatter it. `heldout`, `corpus_update` and `independent` (web questions written by people who had not read the corpus) were not. Always report them separately; a single average hides the difference.
- **Reference answers are written from the gold passage.** They should say what the corpus says, not what is true in general. Where the corpus says little, the reference says so (for example the UPI data-protection question).

The honest limit: I wrote most questions and all reference answers, which biases the set towards how I would phrase things. The independent web questions are the antidote, and only 9 of them were answerable.

---

## 3. Retrieval metrics

Each metric answers a slightly different question about the ranked list of chunks the retriever returns.

| Metric | Question it answers | Range | Blind spot |
|---|---|---|---|
| **Hit@k** | Is *any* relevant chunk in the top k? | 0 to 1 | ignores rank within k and ignores a second relevant chunk |
| **Recall@k** | What *share of the gold passages* did the top k cover? | 0 to 1 | ignores rank within k |
| **MRR** (mean reciprocal rank) | How high is the *first* relevant chunk? Score = 1 / rank | 0 to 1 | ignores everything after the first hit |
| **nDCG@k** | Are *all* relevant chunks ranked high? | 0 to 1 | needs a definition of "relevant"; here binary |

- **Hit@k vs recall@k.** They are equal when a question has one gold passage. With two acceptable passages, finding one gives Hit 1.0 but Recall 0.5. Recall is the stricter number.
- **Why rank matters.** The generator usually sees only the top 3 chunks, and models pay more attention to early text. A relevant chunk at rank 5 may as well not exist for answering, though it still counts for Hit@5.
- **nDCG** gives a relevant chunk at rank r a gain of 1 / log2(r + 1): rank 1 earns 1.0, rank 2 earns 0.63, rank 3 earns 0.5, rank 5 earns 0.39. The sum (DCG) is divided by the best possible sum with every relevant chunk first (the ideal DCG), so a perfect ordering is 1.0.
- **Relevance here is binary and chunk-level:** a chunk is relevant if it contains a gold phrase. Real systems often use graded relevance (highly / somewhat relevant); binary is a simplification.

---

## 4. Worked examples

Take one question with a single relevant chunk, and three results for top-3:

| Ranking (R = relevant) | Hit@3 | Recall@3 | RR (MRR for one question) | nDCG@3 |
|---|---|---|---|---|
| R, -, - | 1 | 1 | 1.00 | 1.00 |
| -, R, - | 1 | 1 | 0.50 | 1 / log2(3) = **0.63** |
| -, -, R | 1 | 1 | 0.33 | 1 / log2(4) = **0.50** |
| -, -, - | 0 | 0 | 0 | 0 |

Hit@3 cannot tell the first three rows apart; MRR and nDCG can.

Now a question with **two** relevant chunks in the index, retrieved at ranks 1 and 3 of the top 3:

- DCG = 1 + 1/log2(4) = 1 + 0.5 = **1.5**
- Ideal DCG = 1 + 1/log2(3) = 1 + 0.631 = **1.631** (both relevant chunks at ranks 1 and 2)
- nDCG@3 = 1.5 / 1.631 = **0.92**

The same retrieval has MRR 1.0 (first hit at rank 1): MRR is blind to the second chunk being at rank 3, nDCG is not.

**Cap by k.** If five relevant chunks exist but only three fit in the top 3, the ideal uses three, so three at the top still scores 1.0.

**Undefined cases.** A question whose gold phrase is in no chunk (the chunker cut it in half) has no relevant chunk; its nDCG is undefined (`nan`) and is skipped rather than counted as 0, and `gold_phrase_intact` reports how often that happens.

---

## 5. Answer metrics

Three questions about a generated answer:

1. **Faithfulness (groundedness).** Split the answer into claims; what share do the retrieved passages support? Outside knowledge does not count, even if true. This catches the model answering from memory or inventing detail. Score = supported claims / all claims.
2. **Answer relevance.** Does the answer address the question that was asked, true or not? "I don't know" is off-topic by this definition.
3. **Correctness against the reference.** Does the answer contain the reference's key facts and nothing that contradicts it? Extra true detail is fine.

They are independent, so each can fail alone:

| Faithful | Relevant | Correct | Example |
|---|---|---|---|
| yes | no | no | Question about a deadline; answer describes the scope of the rule, accurately and from the passage |
| no | yes | yes | Answer is right, but from the model's memory, not the passages: dangerous in a regulated setting because it will be wrong on some other question |
| yes | yes | partial | Answer omits one condition ("up to 2,000 rupees" without "through an authorised card network") |

**Refusals need their own accounting.** A refusal has no claims, so faithfulness is undefined for it. Report:

- *answered share* of answerable questions (the complement is the false-refusal rate);
- *correctness among answered* (quality when it speaks);
- *correctness end to end* (a refusal counts as wrong), which is what a user experiences;
- *correct-refusal rate* on unanswerable questions.

---

## 6. LLM judges and their biases

Faithfulness and correctness need reading comprehension, so a language model is used as the **judge**: given the passages and the answer, return a structured verdict. It is cheap and consistent, and also imperfect:

- **Self-preference.** A model tends to rate text that looks like its own output highly. If the judge is the model that wrote the answers, scores are optimistic. Use a different model as judge, ideally from a different family.
- **Verbosity bias.** Longer, more detailed answers tend to score higher on "completeness" even when padded.
- **Position and format effects.** Order of options and wording of the rubric shift verdicts. A rubric that penalises extra detail will mark good, fuller answers "partial" (this happened in the first smoke test here and the rubric was loosened before the real run).
- **Reasoning models** can be better graders but are slower and reject fixed sampling settings such as temperature 0.

Mitigations used here:

- Judge prompts return **JSON with a closed vocabulary**; anything else is "judge failed", never a made-up score.
- Counts of unparseable judge replies are reported.
- Flagged answers are **listed for a human to read**: the judge is a screening tool, not the truth.
- A **second judge** re-grades the same answers; the two are compared.

**Comparing two judges.** Raw agreement is the share of answers with the same label. It flatters when one label dominates: if 56 of 57 answers are "fully supported", two judges who always say "supported" agree 98% of the time while telling you nothing. **Cohen's kappa** corrects for the agreement chance would give:

```
kappa = (observed agreement - chance agreement) / (1 - chance agreement)
```

1 is perfect, 0 is no better than chance, negative is worse than chance. Kappa becomes undefined or unstable when nearly every item has one label, so read it with the raw number and the list of disagreements. A common rough scale: below 0.4 weak, 0.4 to 0.6 moderate, 0.6 to 0.8 substantial, above 0.8 very strong.

---

## 7. Refusals and the operating point

The answerability check refuses when the passages do not fully answer. That creates a trade-off, not a single best setting:

| Gate | Wrong answers given (unanswerable questions answered) | Right answers withheld (false refusals) |
|---|---|---|
| strict | few | many |
| loose | more | few |

In this repo's run, the strict gate refused 12 of 69 answerable questions and correctly refused 25 of 26 unanswerable ones. Which point is right depends on the cost of each error: in a payments-compliance setting a wrong confident answer is usually worse than "I don't know", but an assistant that refuses one question in six is also hard to use. Decide with numbers and the product's tolerance; do not call either "correct" in the abstract.

---

## 8. Noise and honesty

A score on n questions has sampling error. For a proportion p, the standard error is sqrt(p(1-p)/n), and a rough 95% interval is plus or minus 1.96 times that:

| Score | n | Rough 95% interval |
|---|---|---|
| 0.84 (Hit@3, all answerable) | 69 | about plus or minus 0.09 |
| 0.78 (independent set) | 9 | about plus or minus 0.27 |

So the 69-question number is known to within about 9 points, and the 9-question number to within about 27: a difference of one or two questions is noise. Rules this repo follows:

- Report **n next to every score**, and how many points one question is worth.
- Report **dev, held-out and independent separately**; do not average them.
- Do not change labels after seeing results (the one debatable independent label, iu08, was disclosed, not edited).
- Say what the judge was, and that questions and reference answers were written by the same person.
- Re-run before claiming a small gain; one run cannot show a 3-point improvement.

---

## 9. Latency and cost

- **p95 latency** is the time under which 95% of requests finish; it shows the slow tail that the median hides. Median 2.7 s and p95 4.3 s here: most requests are fine, the slowest few are roughly 60% slower.
- **What counts:** here, search + answerability check + answer (several sequential calls), measured per question and excluding time spent waiting for the rate limit. Retry waits after a 429 error can still inflate the slow tail.
- **Why it is slow-ish:** the pipeline makes at least two model calls in sequence (answerability, then the answer), plus a retry when citations are missing, and the two Azure services are in different regions.
- **Cost per query** is tokens in times price in plus tokens out times price out, summed over every call (including the judge when evaluating). It was not measured yet.

---

## 10. Tools: RAGAS and Azure AI Foundry evaluators

Ready-made libraries implement the same ideas so you do not write judge prompts yourself:

- **RAGAS** is an open-source library with metrics such as faithfulness, answer relevancy, and context precision and recall (does the retrieved context contain what is needed, and how much of it is noise).
- **Azure AI Foundry evaluators** (the `azure-ai-evaluation` package) provide judge-based evaluators such as groundedness and relevance, plus others, and run in Azure tooling. Check the current documentation for names and arguments, because they change between versions.

In this repo's cross-check the Foundry similarity-to-reference score tracked the correctness judge well, while its relevance score gave short correct answers only 3 or 4 and its groundedness gave every answer 5 (see `week-05.md`). A ready-made evaluator is a second opinion, not an authority: check which of its scores separate good answers from weak ones on your data before using one as a gate.

Trade-offs: using a standard tool makes your numbers comparable with other teams' and saves effort; writing your own gives you transparent prompts and lets you tailor the rubric (for example "extra detail is fine") but your numbers are harder to compare. Either way, the judge model and rubric must be stated next to the number.

---

## 11. Interview check: can you answer these out loud?

- [ ] Why score retrieval separately from the final answer? *(Because a wrong answer can come from retrieval, generation or both; separate scores tell you what to fix.)*
- [ ] Difference between Hit@k, recall@k, MRR and nDCG, with an example where they disagree. *(Section 4.)*
- [ ] Why use phrases, not chunk ids, as gold passages? *(So changing the chunker does not invalidate the golden set and strategies compare fairly.)*
- [ ] What are faithfulness, answer relevance and correctness, and can one be high while another is low? *(Section 5.)*
- [ ] Why is a judge that is the same model as the generator a problem, and what do you do about it? *(Self-preference; use a different model, compare judges with kappa, read flagged answers.)*
- [ ] Why can 98% agreement between two judges still mean little? *(One label dominates; kappa corrects for chance.)*
- [ ] How do you evaluate refusals, and why is there no single best setting? *(False refusals vs wrong answers; depends on the cost of each.)*
- [ ] How big a difference on a 9-question set is meaningful? *(One question is 11 points; the interval is about plus or minus 27.)*
- [ ] Dev, held-out and independent: why report them separately? *(Dev was used for tuning, so it flatters; independent shows generalisation.)*
- [ ] What is p95 latency and why not report the mean? *(The tail users feel; the mean hides it.)*
- [ ] How would you gate a pull request on these numbers? *(Fixed golden set, thresholds in a file, fail the check if a metric drops by more than the noise; Week 9.)*
