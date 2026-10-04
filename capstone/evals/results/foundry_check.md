58 answers from the generation run, graded by Azure AI Foundry evaluators (`azure-ai-evaluation`) with `gpt-5-mini` as the judge model. Scores are 1 to 5; 3 or more passes (Foundry's default). One run.

## Summary

| Evaluator | Mean (1-5) | Pass rate (3+) | Scored 5 | Scored below 4 |
|---|---|---|---|---|
| groundedness | 5.00 | 58 of 58 | 58 | 0 |
| relevance | 3.91 | 58 of 58 | 4 | 9 |
| similarity | 4.89 | 57 of 57 | 52 | 1 |

## Answers scoring below 5 on groundedness, relevance or similarity (read by hand)

- q01: What is ISO 20022?
  answer: ISO 20022 is a global standard for financial messaging [1]. It provides a common, structured way to exchange payment and settlement information across banks, payment service providers, corporations, and regulators [1]. ISO 20022 standardizes the format of messages so institutions can exchange structured payment information more consistently [2]. It is a messaging standard that most payment systems are adopting and that payment system operators use [3].
  relevance 4: Directly defines ISO 20022, its purpose, scope, and adoption. The answer is accurate and sufficient for a basic definition but lacks deeper technical details or examples, so it's not fully comprehensive.
- q02: What does ISO 20022 improve compared with proprietary formats?
  answer: ISO 20022 improves data quality by using a consistent message structure instead of fragmented, proprietary formats [1]. It helps institutions exchange richer details such as reference information, remittance data, party identification, and payment status updates in a more standard way [1].
  relevance 4: Directly answers the question by stating ISO 20022's improvements—consistent message structure and richer, standardized data (references, remittance, party IDs, status). Accurate and sufficient, though lacks deeper conte
- q03: Which details can a single ISO 20022 payment message carry?
  answer: A single ISO 20022 payment message can include structured information about the originator, beneficiary, amount, currency, purpose, and payment references [1]. It also carries remittance information that explains why a payment was sent [2]. Additionally, it can include status reporting details to track whether a payment is pending, processed, rejected, or settled [2].
  relevance 3: The response directly lists key fields (originator, beneficiary, amount, currency, purpose, remittance, status) relevant to ISO 20022. However, it is incomplete — omitting account/agent identifiers, dates, charges, payme
- q04: What is remittance information?
  answer: Remittance information is structured details that explain why a payment was sent [1].
  relevance 4: The reply directly defines remittance information and its purpose, which answers the question accurately. It's concise but lacks examples or further context, so it's sufficient but not elaborated.
- q05: What is settlement in card payments?
  answer: Settlement is the process where funds move between participating institutions after the transaction is accepted and processed [1]. Settlement occurs after authorization and clearing steps [1]. Settlement involves the actual transfer of money between parties [2].
  relevance 4: The reply directly defines settlement in card payments, notes it follows authorization and clearing, and explains it's the actual transfer of funds. Accurate and sufficient, but lacks deeper details or examples.
- q06: What is the difference between authorization and settlement?
  answer: Authorization is the approval step that checks whether a payment instrument can be used and whether the account has sufficient funds or approval for the transaction [1]. Authorization involves the merchant sending a request to verify that the card is valid and the account can support the transaction [2]. Settlement is the later process where funds move between parties after the transaction is accepted and processed [1]. Settlement occurs after clearing, where transaction details are exchanged through the card network and acquiring/issuing banks for reconciliation [2]. Settlement involves the actual movement of funds between participating institutions [2].
  relevance 4: Directly answers the question by defining both authorization and settlement, explains their sequence and roles (including clearing/reconciliation). Accurate and sufficient; minor specifics like hold durations or reversal
- q08: What happens during a payment dispute?
  answer: A dispute happens when a cardholder challenges a transaction and asks for investigation, reversal, or customer protection due to issues such as fraud, non-receipt, or billing problems [1]. During the investigation, the company may not report the payment as late to a credit reporting company if you paid the undisputed amount on time, charge interest on the disputed amount, or make you pay the disputed charge [2]. The scheme and the banks may investigate customer disputes, chargebacks, or fraud-related exceptions during dispute handling [3].
  relevance 3: The reply explains what a payment dispute is and mentions possible actions (investigation, reporting, interest, bank/scheme involvement), but it’s brief and omits key steps, timelines, merchant responses, provisional cre
- q09: What is an acquirer?
  answer: An acquirer is the bank that handles the merchant's account [1]. The acquirer is also described as the entity to which the merchant sends the information needed to process the card payment [2].
  relevance 4: Directly defines 'acquirer' as the merchant's bank that processes card payments and receives transaction information. Accurate and on-topic, but brief — could add settlement/processing role details for completeness.
- q11: What role does the card network play?
  answer: The card network operates the rules and infrastructure that allow card payments to be authorized, cleared, and settled across banks and merchants [1]. The network connects the participants, including issuers, acquirers, and merchants [2]. The network facilitates the exchange of transaction details during clearing and supports the overall payment lifecycle [3].
  relevance 4: Directly describes the card network’s core functions—rules, infrastructure, connecting issuers/acquirers/merchants, and facilitating authorization, clearing, and settlement. Accurate and sufficient for the question, thou
- q12: Why is strong customer authentication important?
  answer: Strong customer authentication reduces fraud by adding a second layer of verification before a payment or sensitive operation is approved [1]. It helps ensure the person performing the transaction is actually the legitimate account holder [1].
  relevance 4: The response directly answers why strong customer authentication matters by explaining it reduces fraud and verifies the account holder. It is accurate and sufficient but brief, lacking broader context or extra insights.
- q13: What is PCI DSS?
  answer: PCI DSS is a security standard for protecting payment card data [1]. It provides requirements for storing, transmitting, and processing cardholder data securely [1]. PCI DSS is published by the PCI Security Standards Council [2]. It was developed to encourage and enhance payment card account data security [2]. It helps organisations adopt consistent data security measures worldwide [2]. It sets a baseline of technical and operational requirements designed to protect payment account data [2].
  relevance 4: The response directly and accurately defines PCI DSS, its publisher, and core scope (protecting, storing/transmitting/processing cardholder data). It is clear and sufficient but lacks deeper context or examples, so not c
- q14: What topics does public RBI guidance cover?
  answer: Public RBI guidance covers safe and secure digital payments [1]. It includes customer authentication and fraud controls [1]. It addresses payment infrastructure and processing ecosystem (not confirmed) [1]. It mentions system resilience and operational continuity (not confirmed) [1]. It covers risk management and compliance expectations [1]. It explains the direction of payment systems, consumer protection, digital payments, and risk management in the Indian context [2]. It focuses on reducing fraud, improving security, and making digital payments reliable [3].
  relevance 4: The response directly answers the question by listing key RBI guidance topics—authentication, fraud controls, infrastructure, resilience, risk management, and consumer protection. Minor uncertainty notes and some repetit
- q15: Why do payment systems need good chunking and retrieval?
  answer: Payment systems need good chunking and retrieval because payment documentation is dense, structured, and often spread across standards, rules, and guidance [1]. Good retrieval depends on preserving section boundaries and technical context so the system can answer questions grounded in the correct policy or rule [1].
  relevance 4: The response directly answers why chunking and retrieval are needed, citing dense, structured payment documentation and the need to preserve section boundaries and context for correct, grounded answers.
- q20: Which bank looks after the shop's account?
  answer: The bank that handles the merchant's account is called the Acquirer [2].
  relevance 4: The response correctly identifies the acquiring bank called the Acquirer as the institution that handles a shop's merchant account. It's accurate and directly answers the question but is brief and lacks extra context.
- q23: What are the steps a card payment goes through?
  answer: The steps a card payment goes through are: Authorization, Clearing, Settlement, and Dispute handling [1]. Authorization is when the merchant sends a request to verify that the card is valid and the account can support the transaction [1]. Clearing is when the transaction details are exchanged through the card network and acquiring/issuing banks so the payment can be reconciled [1]. Settlement is when funds move between participating institutions after the transaction is accepted and processed [1]. Dispute handling is when the scheme and the banks may investigate customer disputes, chargebacks, or fraud-related exceptions [1].
  relevance 4: The response directly answers the question by listing and briefly explaining the main stages (authorization, clearing, settlement, dispute handling). It’s accurate and sufficient but lacks deeper operational detail.; similarity 4: Predicted answer includes the same three core steps (Authorization, Clearing, Settlement) with accurate descriptions and adds an extra step (Dispute handling). It matches the correct answer closely but includes additiona
- q24: Why do public regulators publish guidance on digital payments?
  answer: Public regulators publish guidance on digital payments to reduce fraud [1]. They also aim to improve security [1]. Another reason is to make digital payments reliable for consumers and financial institutions [1].
  relevance 4: Directly answers the question by listing key reasons—reducing fraud, improving security, and ensuring reliability. It's relevant and accurate but brief, lacking broader context or additional regulatory motives.
- q25: Who does PCI DSS apply to?
  answer: PCI DSS applies to any entity that stores, processes, or transmits cardholder data (CHD) or sensitive authentication data (SAD) [1]. It also applies to any entity that could affect the security of the cardholder data environment (CDE) [1]. This includes every kind of participant in card processing: merchants, processors, acquirers, issuers, and service providers [1].
  relevance 4: Directly answers who PCI DSS applies to, naming covered data (CHD/SAD), the CDE scope, and listing relevant entities (merchants, processors, acquirers, issuers, service providers). Accurate, clear, and sufficiently compl
- q26: What is the purpose of PCI DSS?
  answer: PCI DSS is a security standard for protecting payment card data [1]. It was developed to encourage and enhance payment card account data security [2]. It helps organisations around the world adopt consistent data security measures [2]. It sets a baseline of technical and operational requirements designed to protect payment account data [2].
  relevance 4: Directly answers the question by stating PCI DSS's purpose — protecting payment card/account data, promoting consistent security measures, and defining baseline technical and operational requirements. It is accurate and
- q27: Which organisations decide whether a company meets the card data security rules?
  answer: Organisations that manage compliance programmes decide whether a company meets the card data security rules [1]. These organisations include a payment brand, an acquirer, or another entity [1]. The PCI Security Standards Council publishes the PCI DSS but does not enforce compliance [1][2].
  relevance 4: The response directly answers the question by naming who decides (payment brands, acquirers, or other entities managing compliance) and adds useful context that the PCI SSC publishes standards but doesn't enforce them.
- q28: When did strong customer authentication become mandatory under PSD2?
  answer: Strong customer authentication (SCA) became mandatory on 13 September 2019 under PSD2 [1].
  relevance 4: The response directly answers the user's question with a precise date when SCA became mandatory under PSD2. It is clear and concise, though it omits contextual details such as later enforcement extensions or practical ro
- q29: What are the aims of PSD2?
  answer: PSD2 aims to make internet payment services easier and safer [1]. It aims to better protect consumers against fraud, abuse, and payment problems [1]. It aims to promote innovative mobile and internet payment services [1]. It aims to strengthen consumer rights [1]. PSD2 also aims to increase competition and choice for consumers by introducing new payment service providers beyond banks [2]. It aims to strengthen the role of the European Banking Authority (EBA) [2]. It aims to limit fees for consumer debit and credit card transactions [3]. It bans retailer surcharges for card use [3].
  relevance 4: The response directly lists PSD2's main aims—consumer protection, competition, innovation, stronger EBA role, fee limits and ban on surcharges. It accurately and sufficiently answers the question but offers limited addit
- q30: Can shops charge extra for paying by card in the EU?
  answer: Shops cannot charge extra fees for paying by card in the EU [1]. The directive bans retailer surcharges for card use [1]. This is part of consumer protection measures under PSD2 [1].
  relevance 4: Directly answers the question stating retailers cannot surcharge card payments in the EU and cites PSD2. Accurate and sufficient for a short reply, but lacks nuance and exceptions (e.g., corporate cards), so not fully co
- q32: Below what value can extra authentication be relaxed for online card payments in India?
  answer: Extra authentication can be relaxed for online card payments in India up to ₹2,000 [1][3].
  relevance 4: The response directly answers the question by giving the specific threshold (₹2,000) for relaxing extra authentication on online card payments in India. It is clear and sufficient but lacks additional context or explanat
- q34: Who is liable if there is a security breach of the card authentication solution?
  answer: Banks and networks bear full liability for any security breach or compromise of the card authentication solution [1].
  relevance 3: Directly answers by naming banks and networks as liable, but it's oversimplified and incomplete — liability often depends on contracts, issuers/acquirers, merchants, and legal/regulatory specifics, so more nuance is need
- q35: How long do I have to dispute a credit card charge in the US?
  answer: You must send a written billing error notice to the card company within 60 calendar days after the charge appeared on your statement [1].
  relevance 4: Directly answers the user's question with the correct 60-day timeframe under US law. Accurate and concise, though it lacks brief context or exceptions (e.g., from date of statement, not charge) that would make it more co
- q36: What must the card company do if my billing complaint is right?
  answer: If your billing complaint is right, the card company must remove the charge from your bill [2].
  relevance 3: Directly answers that the charge must be removed, so it's on-topic, but it's minimal. It omits other required actions (refunds, correcting statements, interest/fee adjustments, or notification), making it incomplete.
- q37: How long does the card company have to acknowledge a billing dispute?
  answer: The card company has 30 days to send a letter confirming that it received the dispute after receiving the notice [1].
  relevance 4: Directly answers the question with a clear 30-day timeframe and method (written acknowledgement). It's accurate and sufficient but lacks extra context or exceptions (e.g., jurisdiction or next steps).; similarity 4: The predicted answer conveys the same main requirement (30 days to send a confirmation letter) but omits the caveat (“unless it has already finished resolving it within that time”), so it is mostly but not completely equ
- q38: What is UPI?
  answer: UPI is an instant, real-time payment system developed by NPCI, the National Payments Corporation of India [1]. It enables inter-bank transactions through mobile phones [1]. Money moves directly from one bank account to another without needing a wallet top-up [1]. Payments work 24/7, including Sundays and bank holidays [1].
  relevance 4: Direct, accurate definition listing NPCI, inter-bank mobile transactions, wallet-free transfers, and 24/7 availability; it addresses the question clearly and provides essential features.
- q39: Can I send money on a bank holiday in India?
  answer: Payments work around the clock, including Sundays and bank holidays [1].
  relevance 4: The reply directly answers the user's question by stating payments work 24/7 including bank holidays. It's relevant and sufficient for a general query, though it omits specifics about transfer methods or bank exceptions.
- q40: What are the two authentication factors in UPI?
  answer: The two authentication factors in UPI are the mobile number linked to the user's bank account and the UPI PIN [1]. These follow the RBI's two-factor authentication rule [1].
  relevance 4: The response directly answers the question by listing the two factors — the mobile number linked to the bank account and the UPI PIN — and cites RBI two-factor authentication. It's accurate and sufficiently complete.
- q41: What does pacs mean in ISO 20022?
  answer: Pacs means payments clearing and settlement in ISO 20022 [1]. It includes messages that support clearing and settlement between financial institutions [1].
  relevance 4: Directly answers the question accurately: 'pacs' denotes the payments clearing and settlement message category in ISO 20022 and notes their role between financial institutions. It's correct and sufficient but concise, la
- q42: How is an ISO 20022 message identifier structured?
  answer: An ISO 20022 message identifier has four parts: four letters for the business area, three digits for the message definition, three digits for the variant, and two digits for the version [1]. The four-letter code represents the business area and is the start of every message identifier [2].
  relevance 4: The reply directly answers the question by listing the four identifier components and mapping each to their meaning; it's accurate and sufficient, though terse and could include an example or separator notation.
- q43: Which ISO 20022 messages deal with reporting account balances and investigations?
  answer: The ISO 20022 messages that deal with reporting account balances and investigations are camt messages [1].
  relevance 3: Identifies the correct ISO 20022 family (camt) that covers account reporting and investigations, but is too brief and omits specific message types (e.g., camt.052, camt.053, camt.029) and details.
- h01: Which regulator issued the circular on online card payments made without a physical card?
  answer: The Reserve Bank of India issued the circular on online card payments made without a physical card [1][3].
  relevance 4: Direct, accurate answer: identifies the Reserve Bank of India as issuer. It fully addresses the user's specific question but provides no additional context or explanation, so it's sufficient but not insightful.
- h03: What is the cardholder data environment?
  answer: The cardholder data environment (CDE) is the systems and processes that handle cardholder data (CHD) [1].
  relevance 3: Answer is directly relevant and accurate but overly brief. It defines CDE as systems and processes handling cardholder data but omits PCI DSS specifics (people, boundaries, connected systems) and examples, so it's incomp
- h04: Can I still dispute a credit card charge after I have paid the bill?
  answer: You can dispute a charge even if you have already paid it [1][2]. Reimbursement may take longer if you have paid the bill [1].
  relevance 4: The response directly answers the question—confirming you can dispute after paying and noting reimbursement may take longer. It is accurate and sufficient for a brief reply but omits procedural details, timelines, or rig
- h05 [also flagged by one of my judges]: Which apps let me link several bank accounts for instant transfers in India?
  answer: Apps like BHIM, PhonePe, and Google Pay let you link several bank accounts for instant transfers in India [1].
  relevance 3: The reply directly names apps (BHIM, PhonePe, Google Pay) that support linking multiple bank accounts for instant UPI transfers in India, but it's brief and omits other common apps and useful context or limits.
- h06: What do the digits in an ISO 20022 message identifier stand for?
  answer: The three digits after the four letters represent the message definition [1]. The next three digits represent the variant [1]. The last two digits represent the version [1].
  relevance 4: The response directly explains the meaning of each digit group in an ISO 20022 identifier (three-digit message definition, three-digit variant, two-digit version). It answers the user's question clearly, though without e; similarity 4: The predicted answer correctly identifies the three-digit message definition, the three-digit variant, and the two-digit version and references the initial four letters; it omits explicitly stating that the four letters
- h07: What is a velocity check?
  answer: A velocity check means limits on how often transactions can happen [1].
  relevance 3: The response gives a concise definition that a velocity check limits transaction frequency, so it's relevant, but it's minimal and lacks context, examples, or explanation of purpose and usage.
- h08: What is strong customer authentication meant to confirm about the person paying?
  answer: Strong customer authentication is meant to confirm that the person performing the transaction is actually the legitimate account holder [1].
  relevance 4: The response directly answers the question by stating SCA confirms the payer is the legitimate account holder. It's concise and accurate, though it omits brief context on how SCA verifies identity.
- h10: When was agreement reached on the update to the EU payments directive?
  answer: Agreement on the update to the EU payments directive was reached on 27 November 2025 [2].
  relevance 4: The response directly answers the user's 'when' question with a specific date. It is sufficient for a simple timing query, though it provides no additional context or explanation.
- h11: Do I need to register a payee before sending money by UPI?
  answer: No, a user can send money to a UPI ID, a mobile number or a QR code without first adding the beneficiary or waiting for approval [1].
  relevance 4: Directly answers the question with a clear 'No' and explains you can send to a UPI ID, mobile number, or QR code without adding the beneficiary, covering the essential information.
- h12: Is the cardholder's agreement needed for the simplified online card payment in India?
  answer: Yes, the cardholder's consent is required for card-not-present transactions up to ₹2,000 under the simplified solution [1].
  relevance 4: Directly answers the question by confirming consent is required and specifying the ₹2,000 limit for card-not-present simplified payments. It's clear and sufficient but lacks regulatory citation or procedural details.
- n01: When must payment providers comply with the RBI authentication directions?
  answer: Payment system providers must comply with the RBI authentication directions by 1 April 2026 unless a provision says otherwise [1].
  relevance 4: The reply directly states the compliance deadline (1 April 2026) and notes possible exceptions, giving a clear and sufficient answer that directly addresses when payment providers must comply.
- n03: Is the relaxation for small online card payments still in force?
  answer: The relaxation for small online card payments up to ₹2,000 was introduced in 2016 [1][2]. This circular was repealed by the RBI authentication directions in 2025 [3]. Therefore, the relaxation is no longer in force [3].
  relevance 4: Directly answers the question: it states the ₹2,000 relaxation began in 2016 and was repealed by RBI authentication directions in 2025, concluding the relaxation is no longer in force.
- n04: By when must card issuers validate cross-border card-not-present transactions?
  answer: Card issuers must validate cross-border card-not-present transactions by 1 October 2026 [1].
  relevance 4: Directly answers the question by giving the exact deadline (1 October 2026). The reply is concise and correct but provides no additional context, sources, or explanation of scope.; similarity 3: Predicted states the deadline and that issuers must validate cross-border CNP transactions, but omits the ‘non-recurring’ qualifier and the requirement to apply risk-based handling to all such transactions, so it is only
- n05: Who pays the customer back if the authentication rules were not followed and money was lost?
  answer: The issuer must compensate the customer in full without demur for a loss that arises from non-compliance with the directions [1].
  relevance 4: Directly answers who is responsible — the issuer — and states they must fully compensate for losses due to non-compliance. The reply is accurate and sufficient but offers no additional context or legal nuance.
- nu1 [also flagged by one of my judges]: What penalty does a bank face for breaching the RBI authentication directions?
  answer: The bank must compensate the customer in full without demur for a loss that arises from non-compliance with the directions [1].
  relevance 4: Directly answers that the bank must fully compensate customers for losses from non-compliance. It is on-topic and specific but omits additional context about RBI enforcement mechanisms or scope of application.
- i01: What is the difference between authorization and settlement in credit card transactions?
  answer: Authorization is the approval step that checks whether a payment instrument can be used and whether the account has sufficient funds or approval for the transaction [1]. Authorization involves the merchant sending a request to verify that the card is valid and the account can support the transaction [2]. Settlement is the later process where funds move between parties after the transaction is accepted and processed [1]. Settlement occurs after clearing, where transaction details are exchanged through the card network and acquiring/issuing banks for reconciliation [2]. Settlement involves the actual movement of funds between participating institutions [2].
  relevance 4: The response directly and accurately distinguishes authorization (approval/validation) from settlement (post-clearing fund movement), explains merchant/issuer/acquirer roles and clearing, covering essential differences.
- i02: How does a credit or debit card transaction actually work behind the scenes?
  answer: A credit or debit card transaction starts with authorization, where the merchant sends a request to verify the card's validity and account support for the transaction [1]. Next, clearing occurs, during which transaction details are exchanged through the card network and acquiring/issuing banks for payment reconciliation [1]. Then, settlement happens, where funds move between participating institutions after the transaction is accepted and processed [1]. Finally, dispute handling may take place, involving investigation of customer disputes, chargebacks, or fraud-related exceptions by the scheme and banks [1]. Card networks like Visa and Mastercard operate the rules and infrastructure that enable these steps across banks and merchants [2].
  relevance 4: Directly explains key behind-the-scenes steps (authorization, clearing, settlement, disputes) and card networks' role. Accurate and sufficient as an overview, though it omits deeper technical message-flow and timing deta
- i04 [also flagged by one of my judges]: What are all the steps to complete a credit card transaction?
  answer: The steps to complete a credit card transaction are four in total [1]. First, Authorization: the merchant sends a request to verify that the card is valid and the account can support the transaction [1]. Second, Clearing: the transaction details are exchanged through the card network and acquiring/issuing banks so the payment can be reconciled [1]. Third, Settlement: funds move between participating institutions after the transaction is accepted and processed [1]. Fourth, Dispute handling: the scheme and the banks may investigate customer disputes, chargebacks, or fraud-related exceptions [1].
  relevance 4: The response directly lists the core steps—authorization, clearing, settlement, and dispute handling—and briefly explains each. It's accurate and on-topic; minor details like capture/authentication or funding nuances are; similarity 4: Predicted answer includes all three core steps (authorization, clearing, settlement) from the correct answer and only adds an extra, related step (dispute handling). The main content is preserved with additional detail,
- i06: What is the full name of UPI?
  answer: The full name of UPI is Unified Payments Interface [1].
  relevance 4: The reply accurately and directly answers the user's question by giving the full name 'Unified Payments Interface.' It's correct and sufficient, though minimal and lacking additional context or explanation.
- i07: How secure are UPI transactions? What measures are in place to protect user data?
  answer: UPI transactions are secured by RBI's two-factor authentication rule [1]. The first factor is the mobile number linked to the user's bank account [1]. The second factor is the UPI PIN [1]. No other specific data protection measures are mentioned in the provided documents [1][2][3].
  relevance 3: The reply addresses UPI security by citing two-factor authentication but is incomplete and partly inaccurate: it omits encryption, tokenization, device/app security, NPCI safeguards and fraud monitoring, and wrongly fram
- i09: How many days do I have to dispute a credit card charge?
  answer: You have 60 calendar days to send a written billing error notice to the card company after the charge appeared on your statement [2].
  relevance 4: Directly answers the question by stating the 60-calendar-day timeframe and required written notice to the card company. Accurate and sufficient, though it omits additional context or exceptions.

Answers my own judges flagged as not fully supported: h05, i04, nu1. Their Foundry groundedness scores: h05 = 5, i04 = 5, nu1 = 5.
