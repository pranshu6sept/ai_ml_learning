69 answerable golden questions; Azure hybrid search (keyword + vector, no semantic ranker); same chunks, only the embedding model differs. One question is worth 0.014.

| Chunking | Embedding | Hit@1 | Hit@3 | Recall@1 | Recall@3 | Recall@5 | MRR@10 | nDCG@3 | nDCG@5 |
|---|---|---|---|---|---|---|---|---|---|
| fixed | small (1536) | 0.43 | 0.81 | 0.39 | 0.79 | 0.90 | 0.64 | 0.61 | 0.67 |
| fixed | large (3072) | 0.55 | 0.84 | 0.50 | 0.82 | 0.89 | 0.71 | 0.67 | 0.72 |
| structure_aware | small (1536) | 0.62 | 0.84 | 0.58 | 0.82 | 0.91 | 0.75 | 0.72 | 0.77 |
| structure_aware | large (3072) | 0.61 | 0.83 | 0.57 | 0.80 | 0.90 | 0.74 | 0.71 | 0.76 |
