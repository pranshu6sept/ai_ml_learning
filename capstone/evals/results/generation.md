95 golden questions through the real pipeline (Azure hybrid + semantic ranker, answerability check, cited answer). Judge = the same gpt-4.1-mini deployment, so scores are optimistic. One run. One question is worth 0.014 of an answerable-question score.

## Headline

| Measure | Value |
|---|---|
| Answerable questions answered | 57 of 69 (12 false refusals) |
| Faithfulness (mean share of claims supported, answered only) | 0.99 (56 of 57 answers fully supported); meets the 0.9 target |
| Answer relevance (answered only) | 0.96 |
| Correctness vs reference, answered only | 0.96 (53 judged fully correct) |
| Correctness end to end (refusal counts as 0) | 0.80 |
| Unanswerable questions correctly refused | 25 of 26 |
| Latency per question, excluding rate-limit waits (median / p95) | 2.7 s / 4.3 s |
| Judge replies that could not be parsed | {'faithfulness': 0, 'relevance': 0, 'correctness': 0} |

## By question set (answerable questions)

| Set | Answerable | Answered | Faithfulness | Relevance | Correct (answered) | Correct (end to end) |
|---|---|---|---|---|---|---|
| corpus_update | 5 | 5 | 1.00 | 0.90 | 0.90 | 0.90 |
| dev | 43 | 34 | 1.00 | 0.97 | 0.97 | 0.77 |
| heldout | 12 | 11 | 0.95 | 1.00 | 0.95 | 0.88 |
| independent | 9 | 7 | 1.00 | 0.93 | 1.00 | 0.78 |

## Answers to read by hand (not fully correct, not fully supported, or refused)

- q07 FALSE REFUSAL (the passages were judged 'partial'): Who handles card dispute processing?
- q10 FALSE REFUSAL (the passages were judged 'partial'): What does the issuing bank do?
- q16 FALSE REFUSAL (the passages were judged 'partial'): How do banks agree on a common way to exchange payment data?
- q17 FALSE REFUSAL (the passages were judged 'partial'): How can I find out where a payment currently stands?
- q18 FALSE REFUSAL (the passages were judged 'partial'): What if a customer says a purchase on their card was not theirs?
- q19 FALSE REFUSAL (the passages were judged 'partial'): How does money actually move between banks after a purchase is approved?
- q22 FALSE REFUSAL (the passages were judged 'partial'): What do regulators expect banks to do to keep payments working during outages?
- q29 (correctness=partial): What are the aims of PSD2?
  answer: PSD2 aims to make internet payment services easier and safer [1]. It aims to better protect consumers against fraud, abuse, and payment problems [1]. It aims to promote innovative mobile and internet payment services [1]. It aims to strengthen consumer rights [1]. PSD2 also aims to increase competition and choice for consumers by introducing new payment service providers beyond banks [2]. It aims to strengthen the role of the European Banking Authority (EBA) [2]. It aims to limit fees for consumer debit and credit card transactions [3]. It bans retailer surcharges for card use [3].
- q31 FALSE REFUSAL (the passages were judged 'partial'): What is PSD3?
- q32 (correctness=partial): Below what value can extra authentication be relaxed for online card payments in India?
  answer: Extra authentication can be relaxed for online card payments in India up to ₹2,000 [1][3].
- q33 FALSE REFUSAL (the passages were judged 'none'): Do I have to use the simplified online card payment option?
- h02 FALSE REFUSAL (the passages were judged 'partial'): What kinds of firms did the EU payments directive allow besides banks?
- h05 (unsupported: These apps allow instant transfers in India): Which apps let me link several bank accounts for instant transfers in India?
  answer: Apps like BHIM, PhonePe, and Google Pay let you link several bank accounts for instant transfers in India [1].
- h06 (correctness=partial): What do the digits in an ISO 20022 message identifier stand for?
  answer: The three digits after the four letters represent the message definition [1]. The next three digits represent the variant [1]. The last two digits represent the version [1].
- n04 (correctness=partial): By when must card issuers validate cross-border card-not-present transactions?
  answer: Card issuers must validate cross-border card-not-present transactions by 1 October 2026 [1].
- i03 FALSE REFUSAL (the passages were judged 'partial'): How do credit card companies settle payments with the banks in clearing system?
- i05 FALSE REFUSAL (the passages were judged 'partial'): Are UPI payments really secure in India?

## Unanswerable questions that got an answer

- nu1: What penalty does a bank face for breaching the RBI authentication directions?
  answer: The bank must compensate the customer in full without demur for a loss that arises from non-compliance with the directions [1].
