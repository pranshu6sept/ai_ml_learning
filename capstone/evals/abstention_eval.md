Structure-aware chunks, hybrid candidates (top 10), cross-encoder ms-marco-MiniLM-L-6-v2. Nothing tuned except the threshold, which is chosen on the tune set only.

Tune set: 43 answerable, 14 unanswerable. Test set: 12 answerable, 11 unanswerable (2 of them off-topic).

## How well does each score separate answerable from unanswerable? (AUROC)

1.0 is perfect, 0.5 is chance. 'Hard only' leaves out the off-topic questions.

| Signal | Tune | Test | All | All, hard only |
|---|---|---|---|---|
| bm25 | 0.48 | 0.80 | 0.58 | 0.50 |
| embedding | 0.62 | 0.77 | 0.68 | 0.62 |
| hybrid | 0.53 | 0.64 | 0.56 | 0.47 |
| reranker | 0.78 | 0.80 | 0.79 | 0.75 |

## Threshold chosen on the tune set, applied unchanged to the test set

| Signal | Threshold | Tune: answered / refused | Test: answered | Test: refused (hard) | Test: refused (off-topic) | Test balanced accuracy |
|---|---|---|---|---|---|---|
| bm25 | 9.43 | 0.40 / 0.79 | 0.67 (8/12) | 0.78 (7/9) | 1.00 (2/2) | 0.74 |
| embedding | 0.709 | 0.23 / 1.00 | 0.17 (2/12) | 1.00 (9/9) | 1.00 (2/2) | 0.58 |
| hybrid | 0.0318 | 0.95 / 0.21 | 0.92 (11/12) | 0.00 (0/9) | 1.00 (2/2) | 0.55 |
| reranker | 4.41 | 0.60 / 0.93 | 0.42 (5/12) | 1.00 (9/9) | 1.00 (2/2) | 0.71 |

## The trade-off: refusing more unanswerable questions also refuses more answerable ones

Descriptive only (all questions pooled, nothing tuned): for each target share of unanswerable questions refused, the share of answerable questions still answered.

| Refuse this share of unanswerable | Reranker: answerable still answered | Embedding: answerable still answered |
|---|---|---|
| 100% | 0.42 | 0.22 |
| 90% | 0.60 | 0.31 |
| 80% | 0.60 | 0.38 |
| 70% | 0.62 | 0.47 |

## Does reranking improve which chunk comes first? (answerable questions)

| Set | Ordering | Hit@1 | Hit@3 |
|---|---|---|---|
| Dev (43) | hybrid (before) | 0.60 | 0.95 |
| Dev (43) | reranked | 0.74 | 0.95 |
| Held-out (12) | hybrid (before) | 0.58 | 0.92 |
| Held-out (12) | reranked | 0.67 | 1.00 |

## Test-set mistakes with the reranker threshold (4.41)

**Answerable but refused: 7**

- h01 (4.36): Which regulator issued the circular on online card payments made without a physical card?
- h02 (-0.97): What kinds of firms did the EU payments directive allow besides banks?
- h05 (1.37): Which apps let me link several bank accounts for instant transfers in India?
- h07 (2.24): What is a velocity check?
- h10 (2.83): When was agreement reached on the update to the EU payments directive?
- h11 (1.30): Do I need to register a payee before sending money by UPI?
- h12 (1.44): Is the cardholder's agreement needed for the simplified online card payment in India?

**Unanswerable but answered: 0**

- none
