43 answerable questions (28 direct, 15 paraphrased) and 5 the corpus cannot answer. Chunks target about 80 words (4 sentences for semantic). Retrieval is TF-IDF, top-k over all four documents. One question is worth 0.023 of any score.

## Corpus as written (includes the meta sections that list sample questions)

| Strategy | Chunks | Words (min/med/max) | Gold phrase intact | Hit@1 | Hit@3 | Hit@5 | MRR@10 | Hit@3 direct | Hit@3 paraphrase |
|---|---|---|---|---|---|---|---|---|---|
| fixed | 50 | 27/80/80 | 1.00 | 0.42 | 0.77 | 0.84 | 0.61 | 0.79 | 0.73 |
| recursive | 61 | 18/43/84 | 1.00 | 0.40 | 0.65 | 0.79 | 0.55 | 0.71 | 0.53 |
| semantic | 100 | 5/27/77 | 1.00 | 0.23 | 0.58 | 0.70 | 0.42 | 0.61 | 0.53 |
| structure_aware | 61 | 21/47/94 | 1.00 | 0.47 | 0.70 | 0.79 | 0.61 | 0.79 | 0.53 |

| Strategy | Mean top score, answerable | Mean top score, unanswerable | Index build (ms) | Query (ms, mean) |
|---|---|---|---|---|
| fixed | 0.329 | 0.333 | 19.08 | 0.963 |
| recursive | 0.355 | 0.363 | 2.64 | 0.946 |
| semantic | 0.404 | 0.417 | 2.84 | 0.969 |
| structure_aware | 0.353 | 0.395 | 2.84 | 1.043 |

## Meta sections removed at ingestion (Practical RAG relevance, Example questions this helps answer)

| Strategy | Chunks | Words (min/med/max) | Gold phrase intact | Hit@1 | Hit@3 | Hit@5 | MRR@10 | Hit@3 direct | Hit@3 paraphrase |
|---|---|---|---|---|---|---|---|---|---|
| fixed | 46 | 27/80/80 | 1.00 | 0.47 | 0.77 | 0.84 | 0.63 | 0.79 | 0.73 |
| recursive | 57 | 18/42/84 | 1.00 | 0.42 | 0.65 | 0.79 | 0.58 | 0.71 | 0.53 |
| semantic | 92 | 5/28/77 | 1.00 | 0.28 | 0.58 | 0.70 | 0.45 | 0.61 | 0.53 |
| structure_aware | 57 | 21/46/94 | 1.00 | 0.49 | 0.72 | 0.84 | 0.62 | 0.82 | 0.53 |

| Strategy | Mean top score, answerable | Mean top score, unanswerable | Index build (ms) | Query (ms, mean) |
|---|---|---|---|---|
| fixed | 0.322 | 0.334 | 2.86 | 0.949 |
| recursive | 0.345 | 0.368 | 2.68 | 0.97 |
| semantic | 0.390 | 0.421 | 2.71 | 0.988 |
| structure_aware | 0.342 | 0.399 | 2.79 | 0.956 |
