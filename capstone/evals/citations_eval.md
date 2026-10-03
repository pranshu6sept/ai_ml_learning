Re-answered 55 questions the model answered before (same index, retrieval, reranking and top-3 passages).

## 1. Citation coverage (share of sentences that carry a [n])

| Reply | Sentences with a citation |
|---|---|
| Baseline (default prompt) | 76/98 (78%) |
| Strict prompt, before enforcement | 137/140 (98%) |
| After enforcement | 137/137 (100%) (by construction) |

## 2. What enforcement removed

- Sentences dropped for lacking a valid citation: 3 across 3 answers.
- Citation markers removed because the passage number did not exist: 0.
- Answers that became a refusal because no sentence had a valid citation: 0.
- Mean words per answer: baseline 37, strict 38, enforced 37.

## 3. Did the content survive? (answerable questions; judge verdict, an unreliable one)

| | Judged correct |
|---|---|
| Baseline | 52/53 |
| After enforcement | 51/53 |

Of the 2 unanswerable questions the model answered in the baseline run, 2 are still answered after enforcement.

## 4. Answers to read (judge flags them, enforcement dropped sentences, or a correct answer turned into a refusal)

- **q17** (answerable): How can I find out where a payment currently stands?
  - enforced: You can find out where a payment currently stands by understanding the payment lifecycle stages: Authorization, Clearing, Settlement, and Dispute handling [2]. Authorization shows if the card is valid and the account can support the transaction [2]. Clearing i
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
  - enforced: PSD3 is a revision of PSD2 [2]. Legislative proposals for PSD3 were published on 28 June 2023 [2]. A political agreement on the review was reached on 27 November 2025 [2].
  - dropped: nothing
  - judge: supported=False, correct=False
- **q41** (answerable): What does pacs mean in ISO 20022?
  - enforced: It refers to messages that support clearing and settlement between financial institutions [1].
  - dropped: ['Pacs means payments clearing and settlement in ISO 20022.']
  - judge: supported=True, correct=True
- **h11** (answerable): Do I need to register a payee before sending money by UPI?
  - enforced: A user can send money to a UPI ID, a mobile number, or a QR code without first adding the beneficiary or waiting for approval [2].
  - dropped: ['No, you do not need to register a payee before sending money by UPI.']
  - judge: supported=True, correct=True
