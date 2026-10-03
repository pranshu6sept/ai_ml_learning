44 independent questions (9 answerable from the corpus, 35 not), taken from Quora titles and the PCI SSC FAQ page in search order. Reranker gate threshold 4.41 was fixed on the author's own questions.

## 1. How well does each signal separate answerable from unanswerable? (AUROC, 1.0 perfect, 0.5 chance)

| Signal | AUROC |
|---|---|
| Reranker score | 0.83 |
| Model's label (full=2, partial=1, none=0) | 0.92 |
| Label full AND quote verified (yes/no) | 0.80 |

## 2. As a gate

- **Reranker gate (4.41)**: 5/9 answerable answered (4 with the answer in the passages) | 4 wrongly refused | 34/35 unanswerable refused | 1 wrong answers shipped
- **Quote-verified check**: 6/9 answerable answered (6 with the answer in the passages) | 3 wrongly refused | 33/35 unanswerable refused | 2 wrong answers shipped
- Quotes the model made up (said "full", quote not in the passages): 0

## 3. Every answerable question, and every unanswerable one a gate would have answered

- **i01** (answerable): What is the difference between authorization and settlement in credit card transactions?
  - reranker 8.87 (answer); label full, quote found True (answer); evidence has the answer: True
  - top passage: faqs > Payments FAQ starter set > FAQ 1: What is the difference between authorization and settlement?
  - quote: Authorization is the approval step that checks whether a payment instrument can be used and whether the account has sufficient funds or approval for the transaction. Settlement is the later process wh
- **i02** (answerable): How does a credit or debit card transaction actually work behind the scenes?
  - reranker -6.39 (refuse); label full, quote found True (answer); evidence has the answer: True
  - top passage: card_scheme_public_summary > Card scheme public summary > Payment lifecycle
  - quote: 1. Authorization: the merchant sends a request to verify that the card is valid and the account can support the transaction.
- **i03** (answerable): How do credit card companies settle payments with the banks in clearing system?
  - reranker 4.89 (answer); label partial, quote found False (refuse); evidence has the answer: True
  - top passage: card_scheme_public_summary > Card scheme public summary > Payment lifecycle
- **i04** (answerable): What are all the steps to complete a credit card transaction?
  - reranker -0.33 (refuse); label full, quote found True (answer); evidence has the answer: True
  - top passage: card_scheme_public_summary > Card scheme public summary > Payment lifecycle
  - quote: 1. Authorization: the merchant sends a request to verify that the card is valid and the account can support the transaction.
2. Clearing: the transaction details are exchanged through the card network
- **i05** (answerable): Are UPI payments really secure in India?
  - reranker 4.99 (answer); label partial, quote found False (refuse); evidence has the answer: False
  - top passage: upi_overview > NPCI UPI overview > Public summary
- **i06** (answerable): What is the full name of UPI?
  - reranker 3.97 (refuse); label full, quote found True (answer); evidence has the answer: True
  - top passage: upi_overview > NPCI UPI overview > Public summary
  - quote: The Unified Payments Interface, UPI, is an instant, real-time payment system developed by NPCI, the National Payments Corporation of India, an RBI-regulated entity.
- **iu05** (UNANSWERABLE): Do someone uses UPI for regular payments? What are their reviews?
  - reranker 2.71 (refuse); label full, quote found True (answer); evidence has the answer: False
  - top passage: upi_overview > NPCI UPI overview > How people use it
  - quote: UPI is used for bill payments, mobile recharges, loan instalments, insurance premiums and subscriptions.
- **i07** (answerable): How secure are UPI transactions? What measures are in place to protect user data?
  - reranker -0.88 (refuse); label partial, quote found False (refuse); evidence has the answer: True
  - top passage: pci_dss_overview > PCI DSS overview > Public summary
- **i08** (answerable): What is UPI, and how does it work?
  - reranker 7.68 (answer); label full, quote found True (answer); evidence has the answer: True
  - top passage: upi_overview > NPCI UPI overview > Public summary
  - quote: The Unified Payments Interface, UPI, is an instant, real-time payment system developed by NPCI, the National Payments Corporation of India, an RBI-regulated entity. It is designed to enable inter-bank
- **i09** (answerable): How many days do I have to dispute a credit card charge?
  - reranker 7.83 (answer); label full, quote found True (answer); evidence has the answer: True
  - top passage: cfpb_credit_card_disputes > CFPB guidance: disputing a credit card charge (United States) > What the card comp
  - quote: To protect your rights, you must also send a written billing error notice to the card company within 60 calendar days after the charge appeared on your statement.
- **iu08** (UNANSWERABLE): Can I dispute a credit card charge after 60 days?
  - reranker 8.66 (answer); label full, quote found True (answer); evidence has the answer: False
  - top passage: cfpb_credit_card_disputes > CFPB guidance: disputing a credit card charge (United States) > How to dispute
  - quote: To protect your rights, you must also send a written billing error notice to the card company within 60 calendar days after the charge appeared on your statement.
