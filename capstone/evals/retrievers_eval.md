BM25 uses its standard defaults (k1=1.5, b=0.75); nothing was tuned. Stemming is the Snowball English stemmer. Meta sections are removed at ingestion. Chunks target about 80 words.

## Dev set (43 answerable, 5 unanswerable; one question = 0.023)

Used while choosing these fixes, so gains here are optimistic.

| Retrieval | Strategy | Hit@1 | Hit@3 | Hit@5 | MRR@10 | Hit@3 paraphrased |
|---|---|---|---|---|---|---|
| tfidf | fixed | 0.47 | 0.77 | 0.84 | 0.63 | 0.73 |
| tfidf | recursive | 0.42 | 0.65 | 0.79 | 0.58 | 0.53 |
| tfidf | semantic | 0.28 | 0.58 | 0.70 | 0.45 | 0.53 |
| tfidf | structure_aware | 0.49 | 0.72 | 0.84 | 0.62 | 0.53 |
| tfidf+stem | fixed | 0.47 | 0.74 | 0.84 | 0.63 | 0.73 |
| tfidf+stem | recursive | 0.49 | 0.77 | 0.88 | 0.66 | 0.80 |
| tfidf+stem | semantic | 0.35 | 0.70 | 0.79 | 0.53 | 0.67 |
| tfidf+stem | structure_aware | 0.53 | 0.79 | 0.95 | 0.69 | 0.80 |
| bm25 | fixed | 0.42 | 0.77 | 0.88 | 0.60 | 0.73 |
| bm25 | recursive | 0.37 | 0.70 | 0.79 | 0.55 | 0.60 |
| bm25 | semantic | 0.28 | 0.58 | 0.74 | 0.46 | 0.53 |
| bm25 | structure_aware | 0.47 | 0.74 | 0.84 | 0.62 | 0.60 |
| bm25+stem | fixed | 0.42 | 0.74 | 0.84 | 0.60 | 0.73 |
| bm25+stem | recursive | 0.49 | 0.77 | 0.86 | 0.65 | 0.73 |
| bm25+stem | semantic | 0.40 | 0.70 | 0.84 | 0.57 | 0.67 |
| bm25+stem | structure_aware | 0.53 | 0.79 | 0.93 | 0.69 | 0.67 |

## Held-out set (12 answerable, 2 unanswerable; one question = 0.083)

Written before any retrieval change and scored once.

| Retrieval | Strategy | Hit@1 | Hit@3 | Hit@5 | MRR@10 | Hit@3 paraphrased |
|---|---|---|---|---|---|---|
| tfidf | fixed | 0.42 | 0.92 | 0.92 | 0.62 | 0.89 |
| tfidf | recursive | 0.58 | 0.75 | 0.83 | 0.69 | 0.67 |
| tfidf | semantic | 0.75 | 0.83 | 0.92 | 0.81 | 0.78 |
| tfidf | structure_aware | 0.58 | 0.75 | 0.83 | 0.69 | 0.67 |
| tfidf+stem | fixed | 0.42 | 0.75 | 0.92 | 0.60 | 0.67 |
| tfidf+stem | recursive | 0.58 | 0.75 | 0.83 | 0.70 | 0.67 |
| tfidf+stem | semantic | 0.67 | 0.83 | 0.83 | 0.75 | 0.78 |
| tfidf+stem | structure_aware | 0.58 | 0.75 | 0.83 | 0.70 | 0.67 |
| bm25 | fixed | 0.50 | 0.83 | 0.92 | 0.66 | 0.78 |
| bm25 | recursive | 0.50 | 0.83 | 0.83 | 0.66 | 0.78 |
| bm25 | semantic | 0.83 | 0.83 | 0.92 | 0.85 | 0.78 |
| bm25 | structure_aware | 0.58 | 0.83 | 0.83 | 0.70 | 0.78 |
| bm25+stem | fixed | 0.50 | 0.75 | 0.83 | 0.65 | 0.67 |
| bm25+stem | recursive | 0.58 | 0.83 | 0.83 | 0.70 | 0.78 |
| bm25+stem | semantic | 0.67 | 0.83 | 0.92 | 0.78 | 0.78 |
| bm25+stem | structure_aware | 0.58 | 0.83 | 0.83 | 0.70 | 0.78 |

## Independent set (9 answerable, 35 unanswerable; one question = 0.111)

Written by someone who had not read the corpus: the most trustworthy numbers here.

| Retrieval | Strategy | Hit@1 | Hit@3 | Hit@5 | MRR@10 | Hit@3 paraphrased |
|---|---|---|---|---|---|---|
| tfidf | fixed | 0.22 | 0.78 | 1.00 | 0.51 | 0.78 |
| tfidf | recursive | 0.44 | 0.67 | 1.00 | 0.61 | 0.67 |
| tfidf | semantic | 0.22 | 0.67 | 0.78 | 0.46 | 0.67 |
| tfidf | structure_aware | 0.44 | 0.89 | 1.00 | 0.65 | 0.89 |
| tfidf+stem | fixed | 0.22 | 0.56 | 0.78 | 0.45 | 0.56 |
| tfidf+stem | recursive | 0.11 | 0.56 | 0.67 | 0.37 | 0.56 |
| tfidf+stem | semantic | 0.11 | 0.33 | 0.44 | 0.28 | 0.33 |
| tfidf+stem | structure_aware | 0.22 | 0.44 | 0.67 | 0.39 | 0.44 |
| bm25 | fixed | 0.11 | 0.67 | 0.89 | 0.40 | 0.67 |
| bm25 | recursive | 0.33 | 0.67 | 0.89 | 0.54 | 0.67 |
| bm25 | semantic | 0.33 | 0.56 | 0.78 | 0.51 | 0.56 |
| bm25 | structure_aware | 0.44 | 0.67 | 1.00 | 0.62 | 0.67 |
| bm25+stem | fixed | 0.11 | 0.44 | 0.67 | 0.34 | 0.44 |
| bm25+stem | recursive | 0.11 | 0.44 | 0.44 | 0.33 | 0.44 |
| bm25+stem | semantic | 0.11 | 0.33 | 0.33 | 0.28 | 0.33 |
| bm25+stem | structure_aware | 0.22 | 0.44 | 0.56 | 0.37 | 0.44 |

## Dev questions that every strategy missed with plain TF-IDF

| Retrieval | Strategy | Hard questions now in the top 3 (of 5) |
|---|---|---|
| tfidf | fixed | 0 (none) |
| tfidf | recursive | 0 (none) |
| tfidf | semantic | 0 (none) |
| tfidf | structure_aware | 0 (none) |
| tfidf+stem | fixed | 0 (none) |
| tfidf+stem | recursive | 2 (q19, q33) |
| tfidf+stem | semantic | 1 (q33) |
| tfidf+stem | structure_aware | 2 (q19, q33) |
| bm25 | fixed | 0 (none) |
| bm25 | recursive | 0 (none) |
| bm25 | semantic | 0 (none) |
| bm25 | structure_aware | 1 (q41) |
| bm25+stem | fixed | 1 (q33) |
| bm25+stem | recursive | 1 (q33) |
| bm25+stem | semantic | 1 (q33) |
| bm25+stem | structure_aware | 2 (q33, q41) |

## Can the top score tell answerable from unanswerable? (dev set, structure_aware)

A ratio above 1 means unanswerable questions scored higher than answerable ones.

| Retrieval | Mean top score, answerable | Mean top score, unanswerable | Ratio |
|---|---|---|---|
| tfidf | 0.342 | 0.399 | 1.17 |
| tfidf+stem | 0.363 | 0.444 | 1.22 |
| bm25 | 7.942 | 8.600 | 1.08 |
| bm25+stem | 8.194 | 10.447 | 1.27 |
