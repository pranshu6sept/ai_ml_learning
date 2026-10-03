BM25 uses its standard defaults (k1=1.5, b=0.75); nothing was tuned. Stemming is the Snowball English stemmer. Meta sections are removed at ingestion. Chunks target about 80 words.

## Dev set (43 answerable, 5 unanswerable; one question = 0.023)

Used while choosing these fixes, so gains here are optimistic.

| Retrieval | Strategy | Hit@1 | Hit@3 | Hit@5 | MRR@10 | Hit@3 paraphrased |
|---|---|---|---|---|---|---|
| tfidf | fixed | 0.44 | 0.72 | 0.88 | 0.62 | 0.73 |
| tfidf | recursive | 0.42 | 0.65 | 0.79 | 0.57 | 0.53 |
| tfidf | semantic | 0.30 | 0.58 | 0.70 | 0.47 | 0.53 |
| tfidf | structure_aware | 0.49 | 0.72 | 0.86 | 0.63 | 0.53 |
| tfidf+stem | fixed | 0.40 | 0.74 | 0.88 | 0.60 | 0.80 |
| tfidf+stem | recursive | 0.49 | 0.77 | 0.88 | 0.66 | 0.80 |
| tfidf+stem | semantic | 0.37 | 0.70 | 0.77 | 0.55 | 0.67 |
| tfidf+stem | structure_aware | 0.58 | 0.79 | 0.98 | 0.72 | 0.80 |
| bm25 | fixed | 0.40 | 0.77 | 0.86 | 0.59 | 0.73 |
| bm25 | recursive | 0.40 | 0.67 | 0.84 | 0.57 | 0.60 |
| bm25 | semantic | 0.30 | 0.63 | 0.74 | 0.49 | 0.53 |
| bm25 | structure_aware | 0.49 | 0.74 | 0.86 | 0.63 | 0.60 |
| bm25+stem | fixed | 0.40 | 0.74 | 0.84 | 0.59 | 0.73 |
| bm25+stem | recursive | 0.47 | 0.77 | 0.88 | 0.64 | 0.73 |
| bm25+stem | semantic | 0.40 | 0.72 | 0.84 | 0.58 | 0.67 |
| bm25+stem | structure_aware | 0.53 | 0.81 | 0.95 | 0.69 | 0.67 |

## Held-out set (12 answerable, 2 unanswerable; one question = 0.083)

Written before any retrieval change and scored once.

| Retrieval | Strategy | Hit@1 | Hit@3 | Hit@5 | MRR@10 | Hit@3 paraphrased |
|---|---|---|---|---|---|---|
| tfidf | fixed | 0.50 | 0.83 | 0.83 | 0.65 | 0.78 |
| tfidf | recursive | 0.67 | 0.83 | 0.83 | 0.74 | 0.78 |
| tfidf | semantic | 0.75 | 0.83 | 0.92 | 0.81 | 0.78 |
| tfidf | structure_aware | 0.67 | 0.83 | 0.83 | 0.74 | 0.78 |
| tfidf+stem | fixed | 0.42 | 0.75 | 0.83 | 0.58 | 0.67 |
| tfidf+stem | recursive | 0.58 | 0.75 | 0.83 | 0.70 | 0.67 |
| tfidf+stem | semantic | 0.67 | 0.83 | 0.83 | 0.75 | 0.78 |
| tfidf+stem | structure_aware | 0.58 | 0.75 | 0.83 | 0.70 | 0.67 |
| bm25 | fixed | 0.50 | 0.83 | 0.83 | 0.65 | 0.78 |
| bm25 | recursive | 0.58 | 0.83 | 0.83 | 0.70 | 0.78 |
| bm25 | semantic | 0.75 | 0.83 | 0.92 | 0.81 | 0.78 |
| bm25 | structure_aware | 0.67 | 0.83 | 0.83 | 0.75 | 0.78 |
| bm25+stem | fixed | 0.50 | 0.75 | 0.83 | 0.63 | 0.67 |
| bm25+stem | recursive | 0.58 | 0.83 | 0.83 | 0.70 | 0.78 |
| bm25+stem | semantic | 0.67 | 0.83 | 0.92 | 0.78 | 0.78 |
| bm25+stem | structure_aware | 0.58 | 0.83 | 0.83 | 0.70 | 0.78 |

## Dev questions that every strategy missed with plain TF-IDF

| Retrieval | Strategy | Hard questions now in the top 3 (of 5) |
|---|---|---|
| tfidf | fixed | 0 (none) |
| tfidf | recursive | 0 (none) |
| tfidf | semantic | 0 (none) |
| tfidf | structure_aware | 0 (none) |
| tfidf+stem | fixed | 1 (q33) |
| tfidf+stem | recursive | 2 (q19, q33) |
| tfidf+stem | semantic | 1 (q33) |
| tfidf+stem | structure_aware | 2 (q19, q33) |
| bm25 | fixed | 1 (q33) |
| bm25 | recursive | 0 (none) |
| bm25 | semantic | 0 (none) |
| bm25 | structure_aware | 1 (q41) |
| bm25+stem | fixed | 1 (q33) |
| bm25+stem | recursive | 1 (q33) |
| bm25+stem | semantic | 1 (q33) |
| bm25+stem | structure_aware | 3 (q25, q33, q41) |

## Can the top score tell answerable from unanswerable? (dev set, structure_aware)

A ratio above 1 means unanswerable questions scored higher than answerable ones.

| Retrieval | Mean top score, answerable | Mean top score, unanswerable | Ratio |
|---|---|---|---|
| tfidf | 0.348 | 0.398 | 1.14 |
| tfidf+stem | 0.363 | 0.446 | 1.23 |
| bm25 | 7.642 | 8.444 | 1.10 |
| bm25+stem | 7.898 | 10.339 | 1.31 |
