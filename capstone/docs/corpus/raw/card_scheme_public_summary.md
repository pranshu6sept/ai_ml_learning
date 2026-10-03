# Card scheme public summary

## Public summary

Card networks such as Visa and Mastercard operate the rules and infrastructure that allow card
payments to be authorized, cleared, and settled across banks and merchants. Public summaries generally
explain the payment lifecycle without exposing confidential operating details.

## Payment lifecycle

1. Authorization: the merchant sends a request to verify that the card is valid and the account can
   support the transaction.
2. Clearing: the transaction details are exchanged through the card network and acquiring/issuing
   banks so the payment can be reconciled.
3. Settlement: funds move between participating institutions after the transaction is accepted and
   processed.
4. Dispute handling: the scheme and the banks may investigate customer disputes, chargebacks, or
   fraud-related exceptions.

## Core concepts

- Issuer: the bank that issued the card to the customer.
- Acquirer: the bank that handles the merchant's account.
- Merchant: the business receiving payment.
- Network: the scheme or infrastructure connecting the participants.

## Why it matters

The card ecosystem depends on clear rules for transaction authorization, risk checks, settlement, and
customer disputes. Public summaries are useful for explaining these concepts to non-specialists while
keeping the material grounded in general card-industry practices.

## Practical RAG relevance

This source helps a payments assistant answer questions such as:

- What is the difference between authorization and settlement?
- Who handles card dispute processing?
- What role do issuing and acquiring banks play?
- How does a transaction move from a merchant to the card network and back?

## Source note

This is an author-written summary, partly checked on 3 October 2026. The European Central Bank's Glossary of terms
related to payment, clearing and settlement systems (30 September 2008) defines card issuer, card scheme, clearing and
settlement in terms consistent with this summary. It describes the acquirer as the entity to which the merchant sends the
information needed to process the card payment, which is looser than "the bank that handles the merchant's account"
above. The authorization step as described here is consistent only with search-engine summaries of Mastercard pages (the
Mastercard guide returned 403). Visa was not checked for the lifecycle.
