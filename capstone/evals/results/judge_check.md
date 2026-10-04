58 answers given in the generation run, re-graded by `gpt-5-mini` (a different model from the one that wrote them, `gpt-4.1-mini`) with the same prompts and passages. Same questions, same answers: only the judge changes. One run.

## Agreement between the two judges

| What was judged | Raw agreement | Cohen's kappa |
|---|---|---|
| faithfulness (all claims supported or not) | 0.95 | -0.02 |
| relevance (direct / partial / off_topic) | 0.93 | 0.47 |
| correctness (correct / partial / incorrect) | 0.91 | 0.51 |

Kappa corrects agreement for chance (1 = perfect, 0 = no better than chance, n/a = both judges use one label for everything: read the raw number). When almost every answer gets the top label, kappa is unstable and a few disagreements move it a lot.

## Mean scores by judge

| Measure | gpt-4.1-mini (answering model) | gpt-5-mini (different model) |
|---|---|---|
| faithfulness | 0.99 | 0.98 |
| relevance | 0.96 | 0.97 |
| correctness | 0.96 | 0.96 |

## Answers where the judges disagree (read by hand)

- q08 (relevance: direct vs partial): What happens during a payment dispute?
  answer: A dispute happens when a cardholder challenges a transaction and asks for investigation, reversal, or customer protection due to issues such as fraud, non-receipt, or billing problems [1]. During the investigation, the company may not report the payment as late to a credit reporting company if you paid the undisputed amount on time, charge interest on the disputed amount, or make you pay the disputed charge [2]. The scheme and the banks may investigate customer disputes, chargebacks, or fraud-related exceptions during dispute handling [3].
- q29 (correctness: partial vs correct): What are the aims of PSD2?
  answer: PSD2 aims to make internet payment services easier and safer [1]. It aims to better protect consumers against fraud, abuse, and payment problems [1]. It aims to promote innovative mobile and internet payment services [1]. It aims to strengthen consumer rights [1]. PSD2 also aims to increase competition and choice for consumers by introducing new payment service providers beyond banks [2]. It aims to strengthen the role of the European Banking Authority (EBA) [2]. It aims to limit fees for consumer debit and credit card transactions [3]. It bans retailer surcharges for card use [3].
- q37 (correctness: correct vs partial): How long does the card company have to acknowledge a billing dispute?
  answer: The card company has 30 days to send a letter confirming that it received the dispute after receiving the notice [1].
- q40 (relevance: partial vs direct): What are the two authentication factors in UPI?
  answer: The two authentication factors in UPI are the mobile number linked to the user's bank account and the UPI PIN [1]. These follow the RBI's two-factor authentication rule [1].
- h05 (faithfulness: unsupported vs supported; unsupported claims per gpt-4.1-mini: ['These apps allow instant transfers in India'], per gpt-5-mini: []): Which apps let me link several bank accounts for instant transfers in India?
  answer: Apps like BHIM, PhonePe, and Google Pay let you link several bank accounts for instant transfers in India [1].
- h06 (correctness: partial vs correct): What do the digits in an ISO 20022 message identifier stand for?
  answer: The three digits after the four letters represent the message definition [1]. The next three digits represent the variant [1]. The last two digits represent the version [1].
- h07 (correctness: correct vs partial): What is a velocity check?
  answer: A velocity check means limits on how often transactions can happen [1].
- n02 (relevance: partial vs direct; correctness: correct vs partial): How many different checks does an Indian digital payment need to pass?
  answer: An Indian digital payment must pass at least two distinct factors of authentication [1]. These factors can be something the user has, knows, or is, such as a password, OTP, PIN, card, software token, or biometric [1].
- nu1 (faithfulness: supported vs unsupported; unsupported claims per gpt-4.1-mini: [], per gpt-5-mini: ['The bank must compensate the customer in full without demur for a loss that arises from non-compliance with the directions.']; relevance: partial vs direct): What penalty does a bank face for breaching the RBI authentication directions?
  answer: The bank must compensate the customer in full without demur for a loss that arises from non-compliance with the directions [1].
- i04 (faithfulness: supported vs unsupported; unsupported claims per gpt-4.1-mini: [], per gpt-5-mini: ['There are four steps to complete a credit card transaction.']): What are all the steps to complete a credit card transaction?
  answer: The steps to complete a credit card transaction are four in total [1]. First, Authorization: the merchant sends a request to verify that the card is valid and the account can support the transaction [1]. Second, Clearing: the transaction details are exchanged through the card network and acquiring/issuing banks so the payment can be reconciled [1]. Third, Settlement: funds move between participating institutions after the transaction is accepted and processed [1]. Fourth, Dispute handling: the scheme and the banks may investigate customer disputes, chargebacks, or fraud-related exceptions [1].
