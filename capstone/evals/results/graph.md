95 golden questions through the LangGraph pipeline (route, retrieve, grade, optional rewrite, generate with a Pydantic schema, validate) versus the plain `ask` pipeline from Week 5. Same retrieval (Azure hybrid + semantic ranker), same answering model, same judge (gpt-4.1-mini, so scores are optimistic). One run.

## Graph vs plain pipeline

| Measure | Plain `ask` | Graph |
|---|---|---|
| Answerable questions answered | 57 of 69 | 55 of 69 |
| False refusals | 12 | 14 |
| Faithfulness (answered) | 0.99 | 0.98 |
| Answer relevance (answered) | 0.96 | 0.96 |
| Correctness vs reference (answered) | 0.96 | 0.95 |
| Correctness end to end | 0.80 | 0.75 |
| Unanswerable correctly refused | 25 of 26 | 25 of 26 |
| Latency median / p95 (s, excl. rate-limit waits) | 2.7 / 4.3 | 3.5 / 6.0 |

## What the graph did

| Event | Count |
|---|---|
| Search rewritten once after weak evidence | 0 |
| Answer regenerated after failing validation | 7 |
| Validation failures (first draft) | 7 |
| Declined by the router as out of scope | 4 |
| In-scope answerable questions the router declined | 0  |
| Small talk | 0 |
| Model calls per question (excluding the judge) | 2.6 |

## Paths taken

| Path | Questions |
|---|---|
| route:in_scope > retrieve:3 > grade:full > generate > validate:ok | 51 |
| route:in_scope > retrieve:3 > grade:partial > refuse | 20 |
| route:in_scope > retrieve:3 > grade:none > refuse | 13 |
| route:in_scope > retrieve:3 > grade:full > generate > validate:fail > regenerate > validate:repaired | 5 |
| route:out_of_scope > decline | 4 |
| route:in_scope > retrieve:3 > grade:full > generate > validate:fail > regenerate > validate:fail > refuse | 2 |

## By question set (answerable questions)

| Set | Answerable | Answered | Faithfulness | Correct (answered) | Correct (end to end) |
|---|---|---|---|---|---|
| corpus_update | 5 | 5 | 1.00 | 0.80 | 0.80 |
| dev | 43 | 33 | 0.99 | 0.98 | 0.76 |
| heldout | 12 | 11 | 0.91 | 0.91 | 0.83 |
| independent | 9 | 6 | 1.00 | 0.92 | 0.61 |

## False refusals (read by hand)

- q07 FALSE REFUSAL (the passages were judged 'partial'; path route:in_scope > retrieve:3 > grade:partial > refuse): Who handles card dispute processing?
- q10 FALSE REFUSAL (the passages were judged 'partial'; path route:in_scope > retrieve:3 > grade:partial > refuse): What does the issuing bank do?
- q13 FALSE REFUSAL (the answer failed validation: 3 sentence(s) have no valid citation; path route:in_scope > retrieve:3 > grade:full > generate > validate:fail (3 sentence(s) have no valid citation) > regenerate > validate:fail (3 sentence(s) have no valid citation) > refuse): What is PCI DSS?
- q16 FALSE REFUSAL (the passages were judged 'partial'; path route:in_scope > retrieve:3 > grade:partial > refuse): How do banks agree on a common way to exchange payment data?
- q17 FALSE REFUSAL (the passages were judged 'partial'; path route:in_scope > retrieve:3 > grade:partial > refuse): How can I find out where a payment currently stands?
- q18 FALSE REFUSAL (the passages were judged 'partial'; path route:in_scope > retrieve:3 > grade:partial > refuse): What if a customer says a purchase on their card was not theirs?
- q19 FALSE REFUSAL (the passages were judged 'partial'; path route:in_scope > retrieve:3 > grade:partial > refuse): How does money actually move between banks after a purchase is approved?
- q22 FALSE REFUSAL (the passages were judged 'partial'; path route:in_scope > retrieve:3 > grade:partial > refuse): What do regulators expect banks to do to keep payments working during outages?
- q31 FALSE REFUSAL (the passages were judged 'partial'; path route:in_scope > retrieve:3 > grade:partial > refuse): What is PSD3?
- q33 FALSE REFUSAL (the passages were judged 'none'; path route:in_scope > retrieve:3 > grade:none > refuse): Do I have to use the simplified online card payment option?
- h02 FALSE REFUSAL (the passages were judged 'partial'; path route:in_scope > retrieve:3 > grade:partial > refuse): What kinds of firms did the EU payments directive allow besides banks?
- i02 FALSE REFUSAL (the answer failed validation: 4 sentence(s) have no valid citation; path route:in_scope > retrieve:3 > grade:full > generate > validate:fail (4 sentence(s) have no valid citation) > regenerate > validate:fail (4 sentence(s) have no valid citation) > refuse): How does a credit or debit card transaction actually work behind the scenes?
- i03 FALSE REFUSAL (the passages were judged 'partial'; path route:in_scope > retrieve:3 > grade:partial > refuse): How do credit card companies settle payments with the banks in clearing system?
- i05 FALSE REFUSAL (the passages were judged 'partial'; path route:in_scope > retrieve:3 > grade:partial > refuse): Are UPI payments really secure in India?

## Unanswerable questions that got an answer

- nu1: What penalty does a bank face for breaching the RBI authentication directions?
  answer: Issuers, which include banks, must compensate the customer in full without demur for a loss that arises from non-compliance with the RBI authentication directions [1].
