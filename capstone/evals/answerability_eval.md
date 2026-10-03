80 questions (55 answerable, 25 unanswerable), same retrieval, reranking and top-3 passages as evaluate_grounding.py. Reranker gate threshold: 4.41 (tuned there on the tune set).

## 1. How well does each signal separate answerable from unanswerable? (AUROC; 1.0 perfect, 0.5 chance)

| Signal | All 80 | Without u03 and b03 (seen before the check was written) |
|---|---|---|
| Reranker score | 0.79 | 0.80 |
| Model's label (full=2, partial=1, none=0) | 0.97 | 0.97 |
| Label full AND quote verified (yes/no) | 0.91 | 0.91 |
| Verified yes/no, ties broken by reranker score | 0.91 | 0.91 |

## 2. As a gate (what a user would see)

- **Reranker gate (4.41)**, all 80: 31/55 answerable answered (31/31 (100%) with the answer in the passages) | 24 wrongly refused | 24/25 unanswerable refused | 1 wrong answers shipped
- **Reranker gate**, without u03 and b03: 31/55 answerable answered (31/31 (100%) with the answer in the passages) | 24 wrongly refused | 22/23 unanswerable refused | 1 wrong answers shipped
- **Quote-verified check**, all 80: 45/55 answerable answered (45/45 (100%) with the answer in the passages) | 10 wrongly refused | 25/25 unanswerable refused | 0 wrong answers shipped
- **Quote-verified check**, without u03 and b03: 45/55 answerable answered (45/45 (100%) with the answer in the passages) | 10 wrongly refused | 23/23 unanswerable refused | 0 wrong answers shipped

## 3. How often does the model make up a quote?

- Said "full": 45 questions. Of those, the quote was NOT found in the passages: 0.
- Labels given: full 45, partial 19, none 16.

## 4. The two failures seen earlier, and every disagreement between the two gates

- **q04** (answerable, evidence has answer: True): What is remittance information?
  - reranker 3.99 (refuse); model label full, quote found True (answer)
  - quote: Remittance information: structured details that explain why a payment was sent.
- **q09** (answerable, evidence has answer: True): What is an acquirer?
  - reranker 2.74 (refuse); model label full, quote found True (answer)
  - quote: Acquirer: the bank that handles the merchant's account.
- **q11** (answerable, evidence has answer: True): What role does the card network play?
  - reranker 2.89 (refuse); model label full, quote found True (answer)
  - quote: Card networks such as Visa and Mastercard operate the rules and infrastructure that allow card payments to be authorized, cleared, and settled across banks and merchants.
- **q20** (answerable, evidence has answer: True): Which bank looks after the shop's account?
  - reranker -8.43 (refuse); model label full, quote found True (answer)
  - quote: Acquirer: the bank that handles the merchant's account.
- **q23** (answerable, evidence has answer: True): What are the steps a card payment goes through?
  - reranker 2.78 (refuse); model label full, quote found True (answer)
  - quote: 1. Authorization: the merchant sends a request to verify that the card is valid and the account can support the transaction.
2. Clearing: the transaction details are exchanged through the card network
- **u03** (UNANSWERABLE, evidence has answer: False): Which ISO 20022 message type is used for a customer credit transfer?
  - reranker 4.40 (refuse); model label partial, quote found False (refuse)
  - quote: (none)
- **q27** (answerable, evidence has answer: True): Which organisations decide whether a company meets the card data security rules?
  - reranker 0.82 (refuse); model label full, quote found True (answer)
  - quote: Compliance requirements are determined by organisations that manage compliance programmes, such as a payment brand, an acquirer or another entity.
- **q30** (answerable, evidence has answer: True): Can shops charge extra for paying by card in the EU?
  - reranker -7.84 (refuse); model label full, quote found True (answer)
  - quote: It bans retailer surcharges for card use.
- **q31** (answerable, evidence has answer: True): What is PSD3?
  - reranker 4.66 (answer); model label partial, quote found False (refuse)
  - quote: (none)
- **q34** (answerable, evidence has answer: True): Who is liable if there is a security breach of the card authentication solution?
  - reranker 2.45 (refuse); model label full, quote found True (answer)
  - quote: Banks and networks are listed as bearing full liability for any security breach or compromise.
- **q39** (answerable, evidence has answer: True): Can I send money on a bank holiday in India?
  - reranker -0.61 (refuse); model label full, quote found True (answer)
  - quote: Payments work around the clock, including Sundays and bank holidays.
- **h01** (answerable, evidence has answer: True): Which regulator issued the circular on online card payments made without a physical card?
  - reranker 4.29 (refuse); model label full, quote found True (answer)
  - quote: This is a Reserve Bank of India circular dated 6 December 2016 (reference RBI/2016-17/172) on card-not-present (CNP) transactions.
- **h05** (answerable, evidence has answer: True): Which apps let me link several bank accounts for instant transfers in India?
  - reranker 1.37 (refuse); model label full, quote found True (answer)
  - quote: Several bank accounts can be linked in one UPI app, such as BHIM, PhonePe or Google Pay.
- **h07** (answerable, evidence has answer: True): What is a velocity check?
  - reranker 1.92 (refuse); model label full, quote found True (answer)
  - quote: Velocity checks, meaning limits on how often transactions can happen, are recommended.
- **h10** (answerable, evidence has answer: True): When was agreement reached on the update to the EU payments directive?
  - reranker 2.83 (refuse); model label full, quote found True (answer)
  - quote: a political agreement on the review was reached on 27 November 2025
- **h11** (answerable, evidence has answer: True): Do I need to register a payee before sending money by UPI?
  - reranker 1.30 (refuse); model label full, quote found True (answer)
  - quote: A user can send money to a UPI ID, a mobile number or a QR code without first adding the beneficiary or waiting for approval.
- **h12** (answerable, evidence has answer: True): Is the cardholder's agreement needed for the simplified online card payment in India?
  - reranker 1.18 (refuse); model label full, quote found True (answer)
  - quote: The cardholder's consent is required, and the solution is optional for card-not-present transactions up to ₹2,000.
- **a04** (UNANSWERABLE, evidence has answer: False): How many days does a card company have to finish investigating a billing dispute?
  - reranker 6.57 (answer); model label partial, quote found False (refuse)
  - quote: (none)
- **b03** (UNANSWERABLE, evidence has answer: False): What is the maximum customer liability amount in the RBI circular?
  - reranker 2.66 (refuse); model label partial, quote found False (refuse)
  - quote: (none)
