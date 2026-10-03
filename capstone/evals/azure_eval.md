Azure OpenAI embeddings + Azure AI Search hybrid (keyword + vector, fused by Azure). Compare with the local hybrid in embeddings_eval.md.

## dev

| Strategy | Hit@1 | Hit@3 | Hit@5 | MRR@10 | Hit@3 paraphrased | Query (ms) |
|---|---|---|---|---|---|---|
| fixed | 0.44 | 0.88 | 0.95 | 0.67 | 0.87 | 490.367 |
| recursive | 0.53 | 0.86 | 0.91 | 0.69 | 0.73 | 471.55 |
| semantic | 0.40 | 0.81 | 0.88 | 0.61 | 0.67 | 442.382 |
| structure_aware | 0.70 | 0.91 | 0.93 | 0.81 | 0.80 | 464.195 |
| structure_aware+semantic | 0.86 | 0.98 | 0.98 | 0.92 | 0.93 | 462.484 |

## heldout

| Strategy | Hit@1 | Hit@3 | Hit@5 | MRR@10 | Hit@3 paraphrased | Query (ms) |
|---|---|---|---|---|---|---|
| fixed | 0.42 | 0.92 | 0.92 | 0.65 | 0.89 | 439.785 |
| recursive | 0.58 | 0.83 | 1.00 | 0.75 | 0.78 | 391.554 |
| semantic | 0.75 | 0.92 | 1.00 | 0.85 | 0.89 | 439.786 |
| structure_aware | 0.67 | 0.92 | 1.00 | 0.78 | 0.89 | 417.05 |
| structure_aware+semantic | 0.92 | 1.00 | 1.00 | 0.96 | 1.00 | 428.113 |

## corpus_update

| Strategy | Hit@1 | Hit@3 | Hit@5 | MRR@10 | Hit@3 paraphrased | Query (ms) |
|---|---|---|---|---|---|---|
| fixed | 0.40 | 0.40 | 0.60 | 0.45 | 0.00 | 378.433 |
| recursive | 0.40 | 0.40 | 0.40 | 0.46 | 0.00 | 341.745 |
| semantic | 0.40 | 0.40 | 0.40 | 0.42 | 0.00 | 629.688 |
| structure_aware | 0.40 | 0.40 | 0.60 | 0.49 | 0.00 | 402.011 |
| structure_aware+semantic | 0.80 | 1.00 | 1.00 | 0.87 | 1.00 | 459.084 |

## independent

| Strategy | Hit@1 | Hit@3 | Hit@5 | MRR@10 | Hit@3 paraphrased | Query (ms) |
|---|---|---|---|---|---|---|
| fixed | 0.44 | 0.56 | 1.00 | 0.59 | 0.56 | 417.99 |
| recursive | 0.56 | 0.78 | 1.00 | 0.70 | 0.78 | 486.587 |
| semantic | 0.44 | 0.67 | 0.89 | 0.58 | 0.67 | 394.586 |
| structure_aware | 0.33 | 0.67 | 1.00 | 0.58 | 0.67 | 459.005 |
| structure_aware+semantic | 0.78 | 1.00 | 1.00 | 0.87 | 1.00 | 567.788 |
