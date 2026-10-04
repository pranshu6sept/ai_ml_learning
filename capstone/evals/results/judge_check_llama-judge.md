58 answers given in the generation run, re-graded by `llama-judge` (a different model from the one that wrote them, `gpt-4.1-mini`) with the same prompts and passages. Same questions, same answers: only the judge changes. One run.

## Agreement between the two judges

| What was judged | Raw agreement | Cohen's kappa |
|---|---|---|
| faithfulness (all claims supported or not) | 0.95 | -0.02 |
| relevance (direct / partial / off_topic) | 0.93 | 0.47 |
| correctness (correct / partial / incorrect) | 0.91 | 0.51 |

Kappa corrects agreement for chance (1 = perfect, 0 = no better than chance, n/a = both judges use one label for everything: read the raw number). When almost every answer gets the top label, kappa is unstable and a few disagreements move it a lot.

## Mean scores by judge

| Measure | gpt-4.1-mini (answering model) | llama-judge (different model) |
|---|---|---|
| faithfulness | 0.99 | 0.99 |
| relevance | 0.96 | 0.97 |
| correctness | 0.96 | 0.96 |

## Answers where the judges disagree (read by hand)

- q01 (faithfulness: supported vs unsupported; unsupported claims per gpt-4.1-mini: [], per llama-judge: ['It provides a common, structured way to exchange payment and settlement information across banks, payment service providers, corporations, and regulators']): What is ISO 20022?
  answer: ISO 20022 is a global standard for financial messaging [1]. It provides a common, structured way to exchange payment and settlement information across banks, payment service providers, corporations, and regulators [1]. ISO 20022 standardizes the format of messages so institutions can exchange structured payment information more consistently [2]. It is a messaging standard that most payment systems are adopting and that payment system operators use [3].
- q14 (faithfulness: supported vs unsupported; unsupported claims per gpt-4.1-mini: [], per llama-judge: ['It addresses payment infrastructure and processing ecosystem', 'It mentions system resilience and operational continuity']): What topics does public RBI guidance cover?
  answer: Public RBI guidance covers safe and secure digital payments [1]. It includes customer authentication and fraud controls [1]. It addresses payment infrastructure and processing ecosystem (not confirmed) [1]. It mentions system resilience and operational continuity (not confirmed) [1]. It covers risk management and compliance expectations [1]. It explains the direction of payment systems, consumer protection, digital payments, and risk management in the Indian context [2]. It focuses on reducing fraud, improving security, and making digital payments reliable [3].
- q20 (relevance: direct vs partial): Which bank looks after the shop's account?
  answer: The bank that handles the merchant's account is called the Acquirer [2].
- q23 (correctness: correct vs partial): What are the steps a card payment goes through?
  answer: The steps a card payment goes through are: Authorization, Clearing, Settlement, and Dispute handling [1]. Authorization is when the merchant sends a request to verify that the card is valid and the account can support the transaction [1]. Clearing is when the transaction details are exchanged through the card network and acquiring/issuing banks so the payment can be reconciled [1]. Settlement is when funds move between participating institutions after the transaction is accepted and processed [1]. Dispute handling is when the scheme and the banks may investigate customer disputes, chargebacks, or fraud-related exceptions [1].
- q40 (relevance: partial vs direct): What are the two authentication factors in UPI?
  answer: The two authentication factors in UPI are the mobile number linked to the user's bank account and the UPI PIN [1]. These follow the RBI's two-factor authentication rule [1].
- q43 (relevance: partial vs direct): Which ISO 20022 messages deal with reporting account balances and investigations?
  answer: The ISO 20022 messages that deal with reporting account balances and investigations are camt messages [1].
- h05 (faithfulness: unsupported vs supported; unsupported claims per gpt-4.1-mini: ['These apps allow instant transfers in India'], per llama-judge: []): Which apps let me link several bank accounts for instant transfers in India?
  answer: Apps like BHIM, PhonePe, and Google Pay let you link several bank accounts for instant transfers in India [1].
- h06 (correctness: partial vs correct): What do the digits in an ISO 20022 message identifier stand for?
  answer: The three digits after the four letters represent the message definition [1]. The next three digits represent the variant [1]. The last two digits represent the version [1].
- h07 (correctness: correct vs partial): What is a velocity check?
  answer: A velocity check means limits on how often transactions can happen [1].
- n04 (correctness: partial vs correct): By when must card issuers validate cross-border card-not-present transactions?
  answer: Card issuers must validate cross-border card-not-present transactions by 1 October 2026 [1].
- nu1 (relevance: partial vs direct): What penalty does a bank face for breaching the RBI authentication directions?
  answer: The bank must compensate the customer in full without demur for a loss that arises from non-compliance with the directions [1].
- i04 (correctness: correct vs partial): What are all the steps to complete a credit card transaction?
  answer: The steps to complete a credit card transaction are four in total [1]. First, Authorization: the merchant sends a request to verify that the card is valid and the account can support the transaction [1]. Second, Clearing: the transaction details are exchanged through the card network and acquiring/issuing banks so the payment can be reconciled [1]. Third, Settlement: funds move between participating institutions after the transaction is accepted and processed [1]. Fourth, Dispute handling: the scheme and the banks may investigate customer disputes, chargebacks, or fraud-related exceptions [1].
