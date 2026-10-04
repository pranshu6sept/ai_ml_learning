69 answerable golden questions. Same hybrid search (keyword + vector, no semantic ranker) over three indexes. One question is worth 0.014.

| Index | Chunks | Hit@1 | Hit@3 | Recall@1 | Recall@3 | Recall@5 | MRR@10 | nDCG@3 | nDCG@5 |
|---|---|---|---|---|---|---|---|---|---|
| push, fixed chunks | 52 | 0.43 | 0.81 | 0.39 | 0.79 | 0.90 | 0.64 | 0.68 | 0.76 |
| push, structure-aware chunks | 63 | 0.62 | 0.84 | 0.58 | 0.82 | 0.91 | 0.75 | 0.72 | 0.77 |
| indexer (Text Split, 600 chars) | 44 | 0.57 | 0.88 | 0.54 | 0.85 | 0.95 | 0.72 | 0.74 | 0.81 |

Indexer chunks: 44 pages, 167 to 595 characters (median 553). Gold phrase intact inside one indexer chunk for 68 of 69 questions.
