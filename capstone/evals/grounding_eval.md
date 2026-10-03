Azure hybrid retrieval -> local reranker -> `gpt-4.1-mini` with the cited prompt; the same deployment judges.
80 questions: 55 answerable, 25 unanswerable. Gate threshold 4.41 (reranker score), chosen on the tune set only.

## 1. No gate: does the model refuse on its own?

| | Answerable (model answered / refused) | Answered correctly | Unanswerable (model refused / answered) |
|---|---|---|---|
| All questions | 53 / 2 | 52/53 (98%) | 23 / 2 |
| Tune set | 41 / 2 | 40/41 (98%) | 13 / 1 |
| Test set | 12 / 0 | 12/12 (100%) | 10 / 1 |

## 2. Quality of the answers the model gave (no gate)

Judged answers: 55 (judge errors: 0).

| Check | Result |
|---|---|
| Every claim supported by the passages (judge) | 53/55 (96%) |
| Citations point to the passage that states the claim (judge) | 54/55 (98%) |
| Answer has at least one [n] citation | 55/55 (100%) |
| Every [n] is a valid passage number | 55/55 (100%) |
| Sentences carrying a citation | 76/98 (78%) |

## 3. Is a wrong answer a retrieval problem or a generation problem? (answerable, answered)

| Retrieved passages contain the answer? | Questions | Answered correctly |
|---|---|---|
| Yes | 52 | 52/52 (100%) |
| No | 1 | 0/1 (0%) |

## 4. With the gate (what a user would actually see)

| | Answerable: answered / correct | Answerable refused | Unanswerable refused | Unanswerable answered (wrong answers shipped) |
|---|---|---|---|---|
| All questions | 31 / 31 | 24 | 25 | 0 |
| Tune set (threshold fitted here) | 26 / 26 | 17 | 14 | 0 |
| Test set (threshold not fitted here) | 5 / 5 | 7 | 11 | 0 |

## 5. Time per question (this laptop to Azure)

Retrieve (embed + search, two regions) 630 ms; rerank (local CPU) 120 ms; generate 7755 ms.

## 6. Answers to read (judge says unsupported or incorrect, or a refusal that should not have happened)

- **q17** (answerable; evidence has answer: False; score -8.07): How can I find out where a payment currently stands?
  - Reply: To find out where a payment currently stands, you need to understand the stages in the payment lifecycle, which include authorization, clearing, settlement, and dispute handling [2]. Authorization confirms if the payment instrument is valid and funds are available, clearing exchanges transaction det
  - Judge: supported=False, correct=False, claims=['Knowing which stage the payment is in will tell you where it currently stands.']
- **q31** (answerable; evidence has answer: True; score 4.66): What is PSD3?
  - Reply: PSD3 is a revision of the Payment Services Directive (PSD2). Legislative proposals for PSD3 and PSR were published on 28 June 2023, and a political agreement on the review was reached on 27 November 2025 [2].
  - Judge: supported=False, correct=True, claims=['PSD3 is a revision of the Payment Services Directive (PSD2).', 'a political agreement on the review was reached on 27 November 2025']
- **q22** (answerable; evidence has answer: True; score -3.09): What do regulators expect banks to do to keep payments working during outages?
  - Reply: I don't know based on the provided documents.
  - Judge: supported=None, correct=None, claims=None
- **q33** (answerable; evidence has answer: False; score -2.81): Do I have to use the simplified online card payment option?
  - Reply: I don't know based on the provided documents.
  - Judge: supported=None, correct=None, claims=None
