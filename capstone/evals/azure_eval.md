Azure OpenAI embeddings + Azure AI Search hybrid (keyword + vector, fused by Azure). Compare with the local hybrid in embeddings_eval.md.

## dev

| Strategy | Hit@1 | Hit@3 | Hit@5 | MRR@10 | Hit@3 paraphrased | Query (ms) |
|---|---|---|---|---|---|---|
| fixed | 0.47 | 0.84 | 0.98 | 0.67 | 0.80 | 532.999 |
| recursive | 0.51 | 0.86 | 0.93 | 0.69 | 0.73 | 547.0 |
| semantic | 0.40 | 0.81 | 0.91 | 0.61 | 0.67 | 546.711 |
| structure_aware | 0.70 | 0.88 | 0.93 | 0.81 | 0.73 | 469.488 |

## heldout

| Strategy | Hit@1 | Hit@3 | Hit@5 | MRR@10 | Hit@3 paraphrased | Query (ms) |
|---|---|---|---|---|---|---|
| fixed | 0.50 | 0.92 | 0.92 | 0.69 | 0.89 | 504.665 |
| recursive | 0.58 | 0.83 | 1.00 | 0.75 | 0.78 | 440.34 |
| semantic | 0.75 | 0.92 | 1.00 | 0.85 | 0.89 | 592.882 |
| structure_aware | 0.67 | 0.83 | 1.00 | 0.77 | 0.78 | 449.367 |

## corpus_update

| Strategy | Hit@1 | Hit@3 | Hit@5 | MRR@10 | Hit@3 paraphrased | Query (ms) |
|---|---|---|---|---|---|---|
| fixed | 0.40 | 0.40 | 0.60 | 0.45 | 0.00 | 500.579 |
| recursive | 0.40 | 0.40 | 0.40 | 0.48 | 0.00 | 474.777 |
| semantic | 0.40 | 0.40 | 0.40 | 0.43 | 0.00 | 397.34 |
| structure_aware | 0.40 | 0.40 | 0.60 | 0.51 | 0.00 | 430.403 |
