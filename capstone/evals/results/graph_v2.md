95 golden questions through the LangGraph pipeline (route, retrieve, grade, optional rewrite, generate with a Pydantic schema, validate) versus the plain `ask` pipeline from Week 5. Same retrieval (Azure hybrid + semantic ranker), same answering model, same judge (gpt-4.1-mini, so scores are optimistic). One run.

## Graph vs plain pipeline

| Measure | Plain `ask` | Graph |
|---|---|---|
| Answerable questions answered | 57 of 69 | 57 of 69 |
| False refusals | 12 | 12 |
| Faithfulness (answered) | 0.99 | 0.99 |
| Answer relevance (answered) | 0.96 | 0.93 |
| Correctness vs reference (answered) | 0.96 | 0.94 |
| Correctness end to end | 0.80 | 0.78 |
| Unanswerable correctly refused | 25 of 26 | 24 of 26 |
| Latency median / p95 (s, excl. rate-limit waits) | 2.7 / 4.3 | 4.5 / 7.7 |

## What the graph did

| Event | Count |
|---|---|
| Search rewritten once after weak evidence | 34 |
| Answer regenerated after failing validation | 7 |
| Validation failures (first draft) | 7 |
| Declined by the router as out of scope | 5 |
| In-scope answerable questions the router declined | 0  |
| Small talk | 0 |
| Model calls per question (excluding the judge) | 3.4 |

## Paths taken

| Path | Questions |
|---|---|
| route:in_scope > retrieve:3 > grade:full > generate > validate:ok | 49 |
| route:in_scope > retrieve:3 > grade:partial > rewrite > retrieve:3 > grade:partial > refuse | 15 |
| route:in_scope > retrieve:3 > grade:none > rewrite > retrieve:3 > grade:none > refuse | 8 |
| route:in_scope > retrieve:3 > grade:full > generate > validate:fail > regenerate > validate:repaired | 7 |
| route:in_scope > retrieve:3 > grade:none > rewrite > retrieve:3 > grade:partial > refuse | 5 |
| route:out_of_scope > decline | 5 |
| route:in_scope > retrieve:3 > grade:partial > rewrite > retrieve:3 > grade:none > refuse | 3 |
| route:in_scope > retrieve:3 > grade:partial > rewrite > retrieve:3 > grade:full > generate > validate:ok | 2 |
| route:in_scope > retrieve:3 > grade:full > rewrite > retrieve:3 > grade:full > generate > validate:ok | 1 |

## By question set (answerable questions)

| Set | Answerable | Answered | Faithfulness | Correct (answered) | Correct (end to end) |
|---|---|---|---|---|---|
| corpus_update | 5 | 5 | 1.00 | 1.00 | 1.00 |
| dev | 43 | 34 | 1.00 | 0.96 | 0.76 |
| heldout | 12 | 12 | 0.96 | 0.96 | 0.96 |
| independent | 9 | 6 | 1.00 | 0.75 | 0.50 |

## False refusals (read by hand)

- q07 FALSE REFUSAL (the passages were judged 'partial'; path route:in_scope > retrieve:3 > grade:partial > rewrite > retrieve:3 > grade:partial > refuse): Who handles card dispute processing?
- q10 FALSE REFUSAL (the passages were judged 'partial'; path route:in_scope > retrieve:3 > grade:partial > rewrite > retrieve:3 > grade:partial > refuse): What does the issuing bank do?
- q16 FALSE REFUSAL (the passages were judged 'partial'; path route:in_scope > retrieve:3 > grade:partial > rewrite > retrieve:3 > grade:partial > refuse): How do banks agree on a common way to exchange payment data?
- q17 FALSE REFUSAL (the passages were judged 'partial'; path route:in_scope > retrieve:3 > grade:partial > rewrite > retrieve:3 > grade:partial > refuse): How can I find out where a payment currently stands?
- q18 FALSE REFUSAL (the passages were judged 'partial'; path route:in_scope > retrieve:3 > grade:partial > rewrite > retrieve:3 > grade:partial > refuse): What if a customer says a purchase on their card was not theirs?
- q19 FALSE REFUSAL (the passages were judged 'partial'; path route:in_scope > retrieve:3 > grade:partial > rewrite > retrieve:3 > grade:partial > refuse): How does money actually move between banks after a purchase is approved?
- q22 FALSE REFUSAL (the passages were judged 'partial'; path route:in_scope > retrieve:3 > grade:partial > rewrite > retrieve:3 > grade:partial > refuse): What do regulators expect banks to do to keep payments working during outages?
- q31 FALSE REFUSAL (the passages were judged 'none'; path route:in_scope > retrieve:3 > grade:partial > rewrite > retrieve:3 > grade:none > refuse): What is PSD3?
- q33 FALSE REFUSAL (the passages were judged 'partial'; path route:in_scope > retrieve:3 > grade:none > rewrite > retrieve:3 > grade:partial > refuse): Do I have to use the simplified online card payment option?
- i03 FALSE REFUSAL (the passages were judged 'partial'; path route:in_scope > retrieve:3 > grade:partial > rewrite > retrieve:3 > grade:partial > refuse): How do credit card companies settle payments with the banks in clearing system?
- i05 FALSE REFUSAL (the passages were judged 'partial'; path route:in_scope > retrieve:3 > grade:partial > rewrite > retrieve:3 > grade:partial > refuse): Are UPI payments really secure in India?
- i07 FALSE REFUSAL (the passages were judged 'partial'; path route:in_scope > retrieve:3 > grade:partial > rewrite > retrieve:3 > grade:partial > refuse): How secure are UPI transactions? What measures are in place to protect user data?

## Unanswerable questions that got an answer

- nu1: What penalty does a bank face for breaching the RBI authentication directions?
  answer: Issuers, which include banks, must compensate the customer in full without demur for a loss that arises from non-compliance with the RBI authentication directions [1].
- a04: How many days does a card company have to finish investigating a billing dispute?
  answer: The card company has 30 days to send a letter confirming that it received the dispute, unless it has already finished the resolution process within that time [2].
