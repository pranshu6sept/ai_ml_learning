Embedding model: all-MiniLM-L6-v2 (local, 384 dimensions). Hybrid = reciprocal rank fusion (constant 60) of BM25 with stemming and the embeddings. Nothing tuned. Meta sections removed; chunks about 80 words.

## Dev set (43 answerable)

| Retrieval | Strategy | Hit@1 | Hit@3 | Hit@5 | MRR@10 | Hit@3 paraphrased | Query (ms) |
|---|---|---|---|---|---|---|---|
| tfidf (baseline) | fixed | 0.44 | 0.72 | 0.88 | 0.62 | 0.73 | 0.954 |
| tfidf (baseline) | recursive | 0.42 | 0.65 | 0.79 | 0.57 | 0.53 | 0.962 |
| tfidf (baseline) | semantic | 0.30 | 0.58 | 0.70 | 0.47 | 0.53 | 0.953 |
| tfidf (baseline) | structure_aware | 0.49 | 0.72 | 0.86 | 0.63 | 0.53 | 0.99 |
| bm25+stem | fixed | 0.40 | 0.74 | 0.84 | 0.59 | 0.73 | 0.363 |
| bm25+stem | recursive | 0.47 | 0.77 | 0.88 | 0.64 | 0.73 | 0.356 |
| bm25+stem | semantic | 0.40 | 0.72 | 0.84 | 0.58 | 0.67 | 0.356 |
| bm25+stem | structure_aware | 0.53 | 0.81 | 0.95 | 0.69 | 0.67 | 0.36 |
| embedding | fixed | 0.51 | 0.72 | 0.86 | 0.64 | 0.60 | 8.465 |
| embedding | recursive | 0.49 | 0.70 | 0.95 | 0.64 | 0.53 | 8.266 |
| embedding | semantic | 0.44 | 0.63 | 0.77 | 0.57 | 0.47 | 8.535 |
| embedding | structure_aware | 0.56 | 0.88 | 0.95 | 0.72 | 0.73 | 8.436 |
| hybrid (bm25+stem, embedding) | fixed | 0.40 | 0.77 | 0.95 | 0.60 | 0.73 | 9.319 |
| hybrid (bm25+stem, embedding) | recursive | 0.44 | 0.81 | 0.98 | 0.64 | 0.80 | 9.476 |
| hybrid (bm25+stem, embedding) | semantic | 0.40 | 0.79 | 0.95 | 0.60 | 0.73 | 9.946 |
| hybrid (bm25+stem, embedding) | structure_aware | 0.60 | 0.95 | 0.98 | 0.77 | 0.87 | 10.747 |

## Held-out set (12 answerable; one question = 0.083)

Written before any retrieval change.

| Retrieval | Strategy | Hit@1 | Hit@3 | Hit@5 | MRR@10 | Hit@3 paraphrased | Query (ms) |
|---|---|---|---|---|---|---|---|
| tfidf (baseline) | fixed | 0.50 | 0.83 | 0.83 | 0.65 | 0.78 | 1.068 |
| tfidf (baseline) | recursive | 0.67 | 0.83 | 0.83 | 0.74 | 0.78 | 1.036 |
| tfidf (baseline) | semantic | 0.75 | 0.83 | 0.92 | 0.81 | 0.78 | 1.0 |
| tfidf (baseline) | structure_aware | 0.67 | 0.83 | 0.83 | 0.74 | 0.78 | 1.032 |
| bm25+stem | fixed | 0.50 | 0.75 | 0.83 | 0.63 | 0.67 | 0.528 |
| bm25+stem | recursive | 0.58 | 0.83 | 0.83 | 0.70 | 0.78 | 0.538 |
| bm25+stem | semantic | 0.67 | 0.83 | 0.92 | 0.78 | 0.78 | 0.531 |
| bm25+stem | structure_aware | 0.58 | 0.83 | 0.83 | 0.70 | 0.78 | 0.497 |
| embedding | fixed | 0.42 | 0.75 | 0.92 | 0.61 | 0.67 | 8.333 |
| embedding | recursive | 0.50 | 0.75 | 0.92 | 0.66 | 0.78 | 8.67 |
| embedding | semantic | 0.58 | 0.75 | 0.83 | 0.70 | 0.78 | 8.375 |
| embedding | structure_aware | 0.67 | 0.92 | 0.92 | 0.77 | 0.89 | 7.99 |
| hybrid (bm25+stem, embedding) | fixed | 0.25 | 0.83 | 1.00 | 0.53 | 0.78 | 8.562 |
| hybrid (bm25+stem, embedding) | recursive | 0.42 | 1.00 | 1.00 | 0.64 | 1.00 | 8.7 |
| hybrid (bm25+stem, embedding) | semantic | 0.58 | 0.83 | 1.00 | 0.72 | 0.89 | 8.827 |
| hybrid (bm25+stem, embedding) | structure_aware | 0.58 | 0.92 | 1.00 | 0.76 | 0.89 | 9.049 |

## Dev questions every strategy missed with plain TF-IDF

| Retrieval | Strategy | Hard questions in the top 3 (of 5) |
|---|---|---|
| tfidf (baseline) | fixed | 0 (none) |
| tfidf (baseline) | recursive | 0 (none) |
| tfidf (baseline) | semantic | 0 (none) |
| tfidf (baseline) | structure_aware | 0 (none) |
| bm25+stem | fixed | 1 (q33) |
| bm25+stem | recursive | 1 (q33) |
| bm25+stem | semantic | 1 (q33) |
| bm25+stem | structure_aware | 3 (q25, q33, q41) |
| embedding | fixed | 2 (q19, q30) |
| embedding | recursive | 2 (q19, q30) |
| embedding | semantic | 3 (q19, q30, q33) |
| embedding | structure_aware | 3 (q19, q25, q30) |
| hybrid (bm25+stem, embedding) | fixed | 1 (q33) |
| hybrid (bm25+stem, embedding) | recursive | 2 (q30, q33) |
| hybrid (bm25+stem, embedding) | semantic | 3 (q19, q30, q33) |
| hybrid (bm25+stem, embedding) | structure_aware | 5 (q19, q25, q30, q33, q41) |

## Can the top score separate answerable from unanswerable? (AUROC, structure_aware chunks, 55 answerable vs 7 unanswerable)

1.0 means every answerable question scored above every unanswerable one; 0.5 is no better than chance.

| Retrieval | AUROC |
|---|---|
| tfidf (baseline) | 0.48 |
| bm25+stem | 0.45 |
| embedding | 0.57 |
| hybrid (bm25+stem, embedding) | 0.53 |
