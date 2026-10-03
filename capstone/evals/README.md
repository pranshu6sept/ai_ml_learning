# Evaluation questions

The 86 questions in `questions.json`, `questions_heldout.json`, `questions_abstain.json` and
`questions_corpus_update.json` were written by the same author as the documents (an AI assistant working with you), who had
read the documents first. That is the biggest weakness of every score in `notes/week-04.md`: the questions share vocabulary
and assumptions with the corpus.

`questions_independent.json` (44 questions) is a first step: the wording comes from the web (Quora titles and the PCI SSC FAQ
page, each with its source recorded), not from me. It is still not fully independent, because I chose the searches, the
exclusion rule, the answerable/unanswerable labels and the gold phrases, and only 9 of the 44 are answerable from the corpus.
**A set written and labelled by a different person is still the most valuable thing missing.** This page is how to add one.

## How to write independent questions (about 40 minutes for 30 questions)

1. **Do not read the documents first.** Write questions the way a real user, colleague or interviewer would ask them,
   from your own knowledge of payments (card payments, UPI, ISO 20022, PSD2, PCI DSS, disputes, RBI rules).
2. Aim for a mix: about half **answerable** from the corpus, about half **not** (a real user also asks things the
   documents don't cover: fees, limits, penalties, specific message names).
3. For the answerable ones, **only afterwards** open `capstone/docs/corpus/raw/` and find the sentence that answers
   the question. Copy it into `phrase` word for word (case and spacing don't matter). If you can't find an answer,
   it is an unanswerable question: set `"gold": []`.
4. Prefer wording that differs from the documents (paraphrases). Kinds: `direct`, `paraphrase`, `unanswerable`.

## File format

Save as `capstone/evals/questions_independent.json` (any name starting with `questions` is picked up by the checks):

```json
[
  {"id": "i01", "kind": "paraphrase", "question": "Do I need to register a payee before sending money by UPI?",
   "gold": [{"doc": "upi_overview", "phrase": "without first adding the beneficiary or waiting for approval"}]},
  {"id": "iu1", "kind": "unanswerable", "question": "What is the daily UPI limit?", "gold": []}
]
```

`doc` is the file name without `.md` in `capstone/docs/corpus/raw/` (or `faqs`). Keep ids unique.

## Check it

```
uv run pytest capstone/tests/test_corpus.py -k gold
```

This fails and names the question if any `phrase` is not word for word in its document. Then score it:

```
uv run --all-groups python capstone/evals/evaluate_retrievers.py     # local retrieval, no Azure needed
```

Report the independent set **separately** from mine, and compare. If the scores drop a lot on yours, that gap is
how much my question-writing flattered the results.
