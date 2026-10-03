Azure OpenAI embeddings + Azure AI Search hybrid (keyword + vector, fused by Azure). Compare with the local hybrid in embeddings_eval.md.

## dev

| Strategy | Hit@1 | Hit@3 | Hit@5 | MRR@10 | Hit@3 paraphrased | Query (ms) |
|---|---|---|---|---|---|---|
| fixed | 0.44 | 0.88 | 0.95 | 0.67 | 0.87 | 517.293 |
| recursive | 0.53 | 0.86 | 0.91 | 0.69 | 0.73 | 464.242 |
| semantic | 0.40 | 0.81 | 0.88 | 0.61 | 0.67 | 530.084 |
| structure_aware | 0.70 | 0.91 | 0.93 | 0.81 | 0.80 | 459.957 |

## heldout

| Strategy | Hit@1 | Hit@3 | Hit@5 | MRR@10 | Hit@3 paraphrased | Query (ms) |
|---|---|---|---|---|---|---|
| fixed | 0.42 | 0.92 | 0.92 | 0.65 | 0.89 | 602.663 |
| recursive | 0.58 | 0.83 | 1.00 | 0.75 | 0.78 | 436.119 |
| semantic | 0.75 | 0.92 | 1.00 | 0.85 | 0.89 | 451.133 |
| structure_aware | 0.67 | 0.92 | 1.00 | 0.78 | 0.89 | 527.554 |

## corpus_update

| Strategy | Hit@1 | Hit@3 | Hit@5 | MRR@10 | Hit@3 paraphrased | Query (ms) |
|---|---|---|---|---|---|---|
| fixed | 0.40 | 0.40 | 0.60 | 0.45 | 0.00 | 462.372 |
| recursive | 0.40 | 0.40 | 0.40 | 0.46 | 0.00 | 448.423 |
| semantic | 0.40 | 0.40 | 0.40 | 0.42 | 0.00 | 447.359 |
| structure_aware | 0.40 | 0.40 | 0.60 | 0.49 | 0.00 | 553.014 |

## independent

| Strategy | Hit@1 | Hit@3 | Hit@5 | MRR@10 | Hit@3 paraphrased | Query (ms) |
|---|---|---|---|---|---|---|
| fixed | 0.44 | 0.56 | 1.00 | 0.59 | 0.56 | 463.901 |
| recursive | 0.56 | 0.78 | 1.00 | 0.70 | 0.78 | 449.806 |
| semantic | 0.44 | 0.67 | 0.89 | 0.58 | 0.67 | 500.88 |
| structure_aware | 0.33 | 0.67 | 1.00 | 0.58 | 0.67 | 469.53 |
