Structure-aware chunks, one Azure index, three ways to order the candidates. One question is worth 1 divided by the number of answerable questions.

## dev (43 answerable)

| Ordering | Hit@1 | Hit@3 | Hit@5 | MRR@10 | Query (ms) |
|---|---|---|---|---|---|
| hybrid | 0.70 | 0.91 | 0.93 | 0.81 | 553.65 |
| hybrid + local cross-encoder | 0.70 | 0.95 | 0.95 | 0.82 | 559.769 |
| hybrid + Azure semantic ranker | 0.86 | 0.98 | 0.98 | 0.92 | 469.369 |

## heldout (12 answerable)

| Ordering | Hit@1 | Hit@3 | Hit@5 | MRR@10 | Query (ms) |
|---|---|---|---|---|---|
| hybrid | 0.67 | 0.92 | 1.00 | 0.78 | 408.657 |
| hybrid + local cross-encoder | 0.67 | 1.00 | 1.00 | 0.82 | 607.593 |
| hybrid + Azure semantic ranker | 0.92 | 1.00 | 1.00 | 0.96 | 470.047 |

## corpus_update (5 answerable)

| Ordering | Hit@1 | Hit@3 | Hit@5 | MRR@10 | Query (ms) |
|---|---|---|---|---|---|
| hybrid | 0.40 | 0.40 | 0.60 | 0.49 | 365.789 |
| hybrid + local cross-encoder | 0.60 | 0.80 | 0.80 | 0.70 | 554.215 |
| hybrid + Azure semantic ranker | 0.80 | 1.00 | 1.00 | 0.87 | 612.492 |

## independent (9 answerable)

| Ordering | Hit@1 | Hit@3 | Hit@5 | MRR@10 | Query (ms) |
|---|---|---|---|---|---|
| hybrid | 0.33 | 0.67 | 1.00 | 0.58 | 385.57 |
| hybrid + local cross-encoder | 0.67 | 0.89 | 0.89 | 0.80 | 531.011 |
| hybrid + Azure semantic ranker | 0.78 | 1.00 | 1.00 | 0.87 | 534.413 |
