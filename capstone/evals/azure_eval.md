Azure OpenAI embeddings + Azure AI Search hybrid (keyword + vector, fused by Azure). Compare with the local hybrid in embeddings_eval.md.

## dev

| Strategy | Hit@1 | Hit@3 | Hit@5 | MRR@10 | Hit@3 paraphrased | Query (ms) |
|---|---|---|---|---|---|---|
| fixed | 0.44 | 0.84 | 1.00 | 0.66 | 0.87 | 466.469 |
| recursive | 0.53 | 0.86 | 0.93 | 0.70 | 0.73 | 431.542 |
| semantic | 0.42 | 0.86 | 0.91 | 0.62 | 0.73 | 414.31 |
| structure_aware | 0.74 | 0.93 | 0.93 | 0.84 | 0.87 | 397.723 |

## heldout

| Strategy | Hit@1 | Hit@3 | Hit@5 | MRR@10 | Hit@3 paraphrased | Query (ms) |
|---|---|---|---|---|---|---|
| fixed | 0.58 | 0.92 | 1.00 | 0.74 | 0.89 | 391.933 |
| recursive | 0.58 | 0.83 | 1.00 | 0.75 | 0.78 | 461.536 |
| semantic | 0.75 | 0.92 | 1.00 | 0.85 | 0.89 | 371.991 |
| structure_aware | 0.67 | 0.92 | 1.00 | 0.79 | 0.89 | 428.574 |
