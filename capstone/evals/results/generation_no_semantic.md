95 golden questions through the real pipeline (Azure hybrid search, NO semantic ranker, answerability check, cited answer). Judge = the same gpt-4.1-mini deployment, so scores are optimistic. One run. One question is worth 0.014 of an answerable-question score.

## Headline

| Measure | Value |
|---|---|
| Answerable questions answered | 51 of 69 (18 false refusals) |
| Faithfulness (mean share of claims supported, answered only) | 0.98 (49 of 51 answers fully supported); meets the 0.9 target |
| Answer relevance (answered only) | 1.00 |
| Correctness vs reference, answered only | 0.93 (44 judged fully correct) |
| Correctness end to end (refusal counts as 0) | 0.69 |
| Unanswerable questions correctly refused | 25 of 26 |
| Latency per question, excluding rate-limit waits (median / p95) | 2.6 s / 4.6 s |
| Judge replies that could not be parsed | {'faithfulness': 0, 'relevance': 0, 'correctness': 0} |

## By question set (answerable questions)

| Set | Answerable | Answered | Faithfulness | Relevance | Correct (answered) | Correct (end to end) |
|---|---|---|---|---|---|---|
| corpus_update | 5 | 2 | 1.00 | 1.00 | 0.75 | 0.30 |
| dev | 43 | 33 | 0.99 | 1.00 | 0.95 | 0.73 |
| heldout | 12 | 10 | 0.95 | 1.00 | 0.90 | 0.75 |
| independent | 9 | 6 | 1.00 | 1.00 | 0.92 | 0.61 |

## Answers to read by hand (not fully correct, not fully supported, or refused)

- q07 FALSE REFUSAL (the passages were judged 'partial'): Who handles card dispute processing?
- q08 (correctness=partial): What happens during a payment dispute?
  answer: During a payment dispute, the company may not report the payment as late to a credit reporting company if you paid the undisputed amount on time [2]. The company may charge interest on the disputed amount [2]. The company may require you to pay the disputed charge [2].
- q10 FALSE REFUSAL (the passages were judged 'partial'): What does the issuing bank do?
- q11 FALSE REFUSAL (the passages were judged 'partial'): What role does the card network play?
- q16 FALSE REFUSAL (the passages were judged 'partial'): How do banks agree on a common way to exchange payment data?
- q17 FALSE REFUSAL (the passages were judged 'none'): How can I find out where a payment currently stands?
- q18 FALSE REFUSAL (the passages were judged 'partial'): What if a customer says a purchase on their card was not theirs?
- q19 FALSE REFUSAL (the passages were judged 'partial'): How does money actually move between banks after a purchase is approved?
- q20 (unsupported: The acquirer is the bank that looks after the shop's account): Which bank looks after the shop's account?
  answer: The bank that handles the merchant's account is called the acquirer [2]. The acquirer is the bank that looks after the shop's account [2]. The acquirer receives the information needed to process the card payment from the merchant [3].
- q22 FALSE REFUSAL (the passages were judged 'partial'): What do regulators expect banks to do to keep payments working during outages?
- q23 (correctness=partial): What are the steps a card payment goes through?
  answer: The steps a card payment goes through are: Authorization, Clearing, Settlement, and Dispute handling [1].
- q30 FALSE REFUSAL (the passages were judged 'none'): Can shops charge extra for paying by card in the EU?
- q31 FALSE REFUSAL (the passages were judged 'partial'): What is PSD3?
- q32 (correctness=partial): Below what value can extra authentication be relaxed for online card payments in India?
  answer: Extra authentication can be relaxed for online card-not-present transactions up to ₹2,000 [2].
- h02 FALSE REFUSAL (the passages were judged 'none'): What kinds of firms did the EU payments directive allow besides banks?
- h05 (unsupported: These apps allow instant transfers in India): Which apps let me link several bank accounts for instant transfers in India?
  answer: Apps like BHIM, PhonePe, and Google Pay let you link several bank accounts for instant transfers in India [1].
- h06 (correctness=partial): What do the digits in an ISO 20022 message identifier stand for?
  answer: The three digits after the four letters represent the message definition [1]. The next three digits represent the variant [1]. The last two digits represent the version [1].
- h09 FALSE REFUSAL (the passages were judged 'full' but its quote was not found): Does the US dispute guidance deal with chargebacks between the issuing and acquiring banks?
- h12 (correctness=partial): Is the cardholder's agreement needed for the simplified online card payment in India?
  answer: Yes, the cardholder's consent is required for the simplified online card payment in India [3].
- n02 FALSE REFUSAL (the passages were judged 'partial'): How many different checks does an Indian digital payment need to pass?
- n03 FALSE REFUSAL (the passages were judged 'partial'): Is the relaxation for small online card payments still in force?
- n04 (correctness=partial): By when must card issuers validate cross-border card-not-present transactions?
  answer: Card issuers must validate cross-border card-not-present transactions by 1 October 2026 [1].
- n05 FALSE REFUSAL (the passages were judged 'none'): Who pays the customer back if the authentication rules were not followed and money was lost?
- i03 FALSE REFUSAL (the passages were judged 'none'): How do credit card companies settle payments with the banks in clearing system?
- i04 (correctness=partial): What are all the steps to complete a credit card transaction?
  answer: The steps to complete a credit card transaction are authorization, clearing, settlement, and dispute handling [2]. Authorization is when the merchant sends a request to verify that the card is valid and the account can support the transaction [2]. Clearing is when the transaction details are exchanged through the card network and acquiring/issuing banks so the payment can be reconciled [2]. Settlement is when funds move between participating institutions after the transaction is accepted and processed [2]. Dispute handling is when the scheme and the banks may investigate customer disputes, chargebacks, or fraud-related exceptions [2].
- i05 FALSE REFUSAL (the passages were judged 'partial'): Are UPI payments really secure in India?
- i07 FALSE REFUSAL (the passages were judged 'partial'): How secure are UPI transactions? What measures are in place to protect user data?

## Unanswerable questions that got an answer

- a04: How many days does a card company have to finish investigating a billing dispute?
  answer: The card company has 30 days to send a letter confirming that it received the dispute, unless it has already finished the resolution process within that time [2].
