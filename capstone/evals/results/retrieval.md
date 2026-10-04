Golden set: 95 questions, 69 answerable (corpus_update 5, dev 43, heldout 12, independent 9) and 26 to refuse. Ranking metrics use the answerable questions only. One question is worth 0.014 of a score on the full set.

Recall@k is the share of a question's gold passages covered by the top k chunks (a question with two acceptable passages scores 0.5 if only one is found); Hit@k is satisfied by either. nDCG@k rewards putting every relevant chunk high.

## All answerable questions: every retriever x every chunking strategy

| Retriever, strategy | Hit@1 | Hit@3 | Recall@1 | Recall@3 | Recall@5 | MRR@10 | nDCG@3 | nDCG@5 |
|---|---|---|---|---|---|---|---|---|
| tfidf, fixed | 0.43 | 0.75 | 0.41 | 0.72 | 0.81 | 0.61 | 0.56 | 0.61 |
| tfidf, recursive | 0.42 | 0.65 | 0.40 | 0.63 | 0.78 | 0.57 | 0.52 | 0.59 |
| tfidf, semantic | 0.33 | 0.59 | 0.31 | 0.58 | 0.72 | 0.49 | 0.47 | 0.53 |
| tfidf, structure_aware | 0.46 | 0.72 | 0.44 | 0.70 | 0.81 | 0.61 | 0.58 | 0.63 |
| bm25+stem, fixed | 0.35 | 0.68 | 0.33 | 0.64 | 0.81 | 0.55 | 0.50 | 0.57 |
| bm25+stem, recursive | 0.41 | 0.70 | 0.38 | 0.67 | 0.75 | 0.57 | 0.53 | 0.57 |
| bm25+stem, semantic | 0.38 | 0.65 | 0.36 | 0.62 | 0.74 | 0.54 | 0.50 | 0.56 |
| bm25+stem, structure_aware | 0.45 | 0.72 | 0.43 | 0.71 | 0.80 | 0.61 | 0.58 | 0.62 |
| hybrid (bm25+stem, embedding), fixed | 0.36 | 0.75 | 0.35 | 0.72 | 0.88 | 0.58 | 0.54 | 0.62 |
| hybrid (bm25+stem, embedding), recursive | 0.42 | 0.72 | 0.40 | 0.72 | 0.91 | 0.61 | 0.57 | 0.65 |
| hybrid (bm25+stem, embedding), semantic | 0.39 | 0.77 | 0.36 | 0.76 | 0.88 | 0.59 | 0.58 | 0.64 |
| hybrid (bm25+stem, embedding), structure_aware | 0.52 | 0.84 | 0.50 | 0.83 | 0.94 | 0.70 | 0.68 | 0.73 |
| azure hybrid, structure_aware | 0.62 | 0.84 | 0.58 | 0.82 | 0.91 | 0.75 | 0.72 | 0.77 |
| azure hybrid + semantic ranker, structure_aware | 0.86 | 0.99 | 0.82 | 0.97 | 0.97 | 0.92 | 0.90 | 0.91 |

## By question set (structure-aware chunks)

Dev questions were used to build and tune the pipeline, so they flatter it; held-out, corpus_update and independent were not. Small sets are noisy.

### corpus_update (5 questions)

| Retriever | Hit@1 | Hit@3 | Recall@1 | Recall@3 | Recall@5 | MRR@10 | nDCG@3 | nDCG@5 |
|---|---|---|---|---|---|---|---|---|
| tfidf | 0.40 | 0.40 | 0.40 | 0.40 | 0.40 | 0.43 | 0.40 | 0.40 |
| bm25+stem | 0.20 | 0.40 | 0.20 | 0.40 | 0.40 | 0.33 | 0.33 | 0.33 |
| hybrid (bm25+stem, embedding) | 0.40 | 0.40 | 0.40 | 0.40 | 0.60 | 0.47 | 0.40 | 0.48 |
| azure hybrid | 0.40 | 0.40 | 0.40 | 0.40 | 0.60 | 0.49 | 0.40 | 0.48 |
| azure hybrid + semantic ranker | 0.80 | 1.00 | 0.80 | 0.90 | 0.90 | 0.87 | 0.86 | 0.86 |

### dev (43 questions)

| Retriever | Hit@1 | Hit@3 | Recall@1 | Recall@3 | Recall@5 | MRR@10 | nDCG@3 | nDCG@5 |
|---|---|---|---|---|---|---|---|---|
| tfidf | 0.44 | 0.72 | 0.41 | 0.69 | 0.81 | 0.60 | 0.55 | 0.61 |
| bm25+stem | 0.49 | 0.79 | 0.45 | 0.77 | 0.87 | 0.67 | 0.61 | 0.66 |
| hybrid (bm25+stem, embedding) | 0.53 | 0.91 | 0.50 | 0.88 | 0.95 | 0.72 | 0.70 | 0.74 |
| azure hybrid | 0.70 | 0.91 | 0.63 | 0.87 | 0.91 | 0.81 | 0.77 | 0.80 |
| azure hybrid + semantic ranker | 0.86 | 0.98 | 0.80 | 0.97 | 0.97 | 0.92 | 0.89 | 0.90 |

### heldout (12 questions)

| Retriever | Hit@1 | Hit@3 | Recall@1 | Recall@3 | Recall@5 | MRR@10 | nDCG@3 | nDCG@5 |
|---|---|---|---|---|---|---|---|---|
| tfidf | 0.58 | 0.75 | 0.58 | 0.75 | 0.83 | 0.69 | 0.69 | 0.72 |
| bm25+stem | 0.58 | 0.83 | 0.58 | 0.83 | 0.83 | 0.69 | 0.73 | 0.73 |
| hybrid (bm25+stem, embedding) | 0.58 | 0.83 | 0.58 | 0.83 | 1.00 | 0.75 | 0.74 | 0.81 |
| azure hybrid | 0.67 | 0.92 | 0.67 | 0.92 | 1.00 | 0.78 | 0.80 | 0.83 |
| azure hybrid + semantic ranker | 0.92 | 1.00 | 0.92 | 1.00 | 1.00 | 0.96 | 0.97 | 0.97 |

### independent (9 questions)

| Retriever | Hit@1 | Hit@3 | Recall@1 | Recall@3 | Recall@5 | MRR@10 | nDCG@3 | nDCG@5 |
|---|---|---|---|---|---|---|---|---|
| tfidf | 0.44 | 0.89 | 0.44 | 0.89 | 1.00 | 0.65 | 0.70 | 0.74 |
| bm25+stem | 0.22 | 0.44 | 0.22 | 0.44 | 0.67 | 0.38 | 0.35 | 0.44 |
| hybrid (bm25+stem, embedding) | 0.44 | 0.78 | 0.44 | 0.78 | 1.00 | 0.63 | 0.63 | 0.72 |
| azure hybrid | 0.33 | 0.67 | 0.33 | 0.67 | 1.00 | 0.58 | 0.54 | 0.68 |
| azure hybrid + semantic ranker | 0.78 | 1.00 | 0.78 | 1.00 | 1.00 | 0.87 | 0.90 | 0.90 |
