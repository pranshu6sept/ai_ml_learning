95 golden questions through the LangGraph pipeline (route, retrieve, grade, optional rewrite, generate with a Pydantic schema, validate) versus the plain `ask` pipeline from Week 5. Same retrieval (Azure hybrid + semantic ranker), same answering model, same judge (gpt-4.1-mini, so scores are optimistic). One run.

## Graph vs plain pipeline

| Measure | Plain `ask` | Graph |
|---|---|---|
| Answerable questions answered | 57 of 69 | 52 of 69 |
| False refusals | 12 | 17 |
| Faithfulness (answered) | 0.99 | 0.95 |
| Answer relevance (answered) | 0.96 | 0.99 |
| Correctness vs reference (answered) | 0.96 | 0.99 |
| Correctness end to end | 0.80 | 0.75 |
| Unanswerable correctly refused | 25 of 26 | 24 of 26 |
| Latency median / p95 (s, excl. rate-limit waits) | 2.7 / 4.3 | 4.4 / 6.2 |

## What the graph did

| Event | Count |
|---|---|
| Search rewritten once after weak evidence | 32 |
| Answer regenerated after failing validation | 7 |
| Validation failures (first draft) | 7 |
| Declined by the router as out of scope | 6 |
| In-scope answerable questions the router declined | 1 ['q20'] |
| Small talk | 0 |
| Model calls per question (excluding the judge) | 3.3 |

## Paths taken

| Path | Questions |
|---|---|
| route:in_scope > retrieve:3 > grade:full > generate > validate:ok | 50 |
| route:in_scope > retrieve:3 > grade:partial > rewrite > retrieve:3 > grade:partial > refuse | 16 |
| route:in_scope > retrieve:3 > grade:none > rewrite > retrieve:3 > grade:none > refuse | 10 |
| route:out_of_scope > decline | 6 |
| route:in_scope > retrieve:3 > grade:full > generate > validate:fail > regenerate > validate:fail > refuse | 4 |
| route:in_scope > retrieve:3 > grade:full > generate > validate:fail > regenerate > validate:ok | 3 |
| route:in_scope > retrieve:3 > grade:none > rewrite > retrieve:3 > grade:partial > refuse | 3 |
| route:in_scope > retrieve:3 > grade:partial > rewrite > retrieve:3 > grade:none > refuse | 2 |
| route:in_scope > retrieve:3 > grade:partial > rewrite > retrieve:3 > grade:full > generate > validate:ok | 1 |

## False refusals (read by hand)

- q07 FALSE REFUSAL (the passages were judged 'partial'; path route:in_scope > retrieve:3 > grade:partial > rewrite > retrieve:3 > grade:partial > refuse): Who handles card dispute processing?
- q10 FALSE REFUSAL (the passages were judged 'partial'; path route:in_scope > retrieve:3 > grade:partial > rewrite > retrieve:3 > grade:partial > refuse): What does the issuing bank do?
- q12 FALSE REFUSAL (the answer failed validation: 1 sentence(s) have no valid citation; path route:in_scope > retrieve:3 > grade:full > generate > validate:fail (1 sentence(s) have no valid citation) > regenerate > validate:fail (1 sentence(s) have no valid citation) > refuse): Why is strong customer authentication important?
- q15 FALSE REFUSAL (the answer failed validation: 1 sentence(s) have no valid citation; path route:in_scope > retrieve:3 > grade:full > generate > validate:fail (1 sentence(s) have no valid citation) > regenerate > validate:fail (1 sentence(s) have no valid citation) > refuse): Why do payment systems need good chunking and retrieval?
- q16 FALSE REFUSAL (the passages were judged 'partial'; path route:in_scope > retrieve:3 > grade:partial > rewrite > retrieve:3 > grade:partial > refuse): How do banks agree on a common way to exchange payment data?
- q17 FALSE REFUSAL (the passages were judged 'partial'; path route:in_scope > retrieve:3 > grade:partial > rewrite > retrieve:3 > grade:partial > refuse): How can I find out where a payment currently stands?
- q18 FALSE REFUSAL (the passages were judged 'partial'; path route:in_scope > retrieve:3 > grade:partial > rewrite > retrieve:3 > grade:partial > refuse): What if a customer says a purchase on their card was not theirs?
- q19 FALSE REFUSAL (the passages were judged 'partial'; path route:in_scope > retrieve:3 > grade:partial > rewrite > retrieve:3 > grade:partial > refuse): How does money actually move between banks after a purchase is approved?
- q20 FALSE REFUSAL (the question is outside the payments scope; path route:out_of_scope > decline): Which bank looks after the shop's account?
- q22 FALSE REFUSAL (the passages were judged 'partial'; path route:in_scope > retrieve:3 > grade:partial > rewrite > retrieve:3 > grade:partial > refuse): What do regulators expect banks to do to keep payments working during outages?
- q31 FALSE REFUSAL (the passages were judged 'none'; path route:in_scope > retrieve:3 > grade:partial > rewrite > retrieve:3 > grade:none > refuse): What is PSD3?
- q33 FALSE REFUSAL (the passages were judged 'partial'; path route:in_scope > retrieve:3 > grade:none > rewrite > retrieve:3 > grade:partial > refuse): Do I have to use the simplified online card payment option?
- h02 FALSE REFUSAL (the passages were judged 'partial'; path route:in_scope > retrieve:3 > grade:partial > rewrite > retrieve:3 > grade:partial > refuse): What kinds of firms did the EU payments directive allow besides banks?
- h06 FALSE REFUSAL (the answer failed validation: 1 sentence(s) have no valid citation; path route:in_scope > retrieve:3 > grade:full > generate > validate:fail (1 sentence(s) have no valid citation) > regenerate > validate:fail (1 sentence(s) have no valid citation) > refuse): What do the digits in an ISO 20022 message identifier stand for?
- n02 FALSE REFUSAL (the answer failed validation: 1 sentence(s) have no valid citation; path route:in_scope > retrieve:3 > grade:full > generate > validate:fail (1 sentence(s) have no valid citation) > regenerate > validate:fail (1 sentence(s) have no valid citation) > refuse): How many different checks does an Indian digital payment need to pass?
- i03 FALSE REFUSAL (the passages were judged 'partial'; path route:in_scope > retrieve:3 > grade:partial > rewrite > retrieve:3 > grade:partial > refuse): How do credit card companies settle payments with the banks in clearing system?
- i05 FALSE REFUSAL (the passages were judged 'partial'; path route:in_scope > retrieve:3 > grade:partial > rewrite > retrieve:3 > grade:partial > refuse): Are UPI payments really secure in India?

## Unanswerable questions that got an answer

- nu1: What penalty does a bank face for breaching the RBI authentication directions?
  answer: Issuers, which include banks, must compensate the customer in full without demur for any loss that arises from non-compliance with the RBI authentication directions [1].
- a04: How many days does a card company have to finish investigating a billing dispute?
  answer: The card company has 30 days to send a letter confirming that it received the dispute, unless it has already finished the resolution process within that time, implying that the investigation should be completed within 30 days after receiving the notice of dispute [2].
