Re-answered 55 questions the model answered before (same index, retrieval, reranking and top-3 passages).

## 1. Citation coverage (share of sentences that carry a [n])

| Reply | Sentences with a citation |
|---|---|
| Baseline (default prompt) | 76/99 (77%) |
| Strict prompt, before enforcement | 135/141 (96%) |
| After enforcement | 135/135 (100%) (by construction) |

## 2. What enforcement removed

- Sentences dropped for lacking a valid citation: 6 across 5 answers.
- Citation markers removed because the passage number did not exist: 0.
- Answers that became a refusal because no sentence had a valid citation: 0.
- Mean words per answer: baseline 36, strict 38, enforced 37.

## 3. Did the content survive? (answerable questions; judge verdict, an unreliable one)

| | Judged correct |
|---|---|
| Baseline | 52/53 |
| After enforcement | 50/53 |

Of the 2 unanswerable questions the model answered in the baseline run, 2 are still answered after enforcement.

## 4. Answers to read (judge flags them, enforcement dropped sentences, or a correct answer turned into a refusal)

- **q17** (answerable): How can I find out where a payment currently stands?
  - enforced: You can find out where a payment currently stands by understanding the payment lifecycle stages: authorization, clearing, settlement, and dispute handling [2]. Authorization shows if the card is valid and the account can support the transaction [2]. Clearing i
  - dropped: nothing
  - judge: supported=True, correct=False
- **u03** (unanswerable): Which ISO 20022 message type is used for a customer credit transfer?
  - enforced: The ISO 20022 message type used for a customer credit transfer is "pain" [1].
  - dropped: nothing
  - judge: supported=False, correct=None
- **q30** (answerable): Can shops charge extra for paying by card in the EU?
  - enforced: The directive bans retailer surcharges for card use [1].
  - dropped: ['No, shops cannot charge extra for paying by card in the EU.']
  - judge: supported=True, correct=True
- **q31** (answerable): What is PSD3?
  - enforced: A political agreement on the review was reached on 27 November 2025 [2].
  - dropped: ['PSD3 is a revision of PSD2.', 'It is part of legislative proposals published on 28 June 2023.']
  - judge: supported=False, correct=False
- **q39** (answerable): Can I send money on a bank holiday in India?
  - enforced: Payments work around the clock, including Sundays and bank holidays [2].
  - dropped: ['Yes, you can send money on a bank holiday in India.']
  - judge: supported=True, correct=True
- **h02** (answerable): What kinds of firms did the EU payments directive allow besides banks?
  - enforced: This increased competition and choice for consumers [2].
  - dropped: ['The EU payments directive allowed a new category of payment service provider beyond banks.']
  - judge: supported=False, correct=False
- **b03** (unanswerable): What is the maximum customer liability amount in the RBI circular?
  - enforced: The maximum customer liability amount is disclosed at enrolment by banks, but the exact amount is not specified in the passages [1]. The 2016 circular allowed card-not-present transactions up to ₹2,000 without additional authentication, but this does not speci
  - dropped: ['Therefore, the exact maximum customer liability amount is not provided in the passages.']
  - judge: supported=True, correct=None
