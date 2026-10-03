# ISO 20022 message definitions and identifiers

## Public summary

The ISO 20022 repository groups its message definitions into business areas. Each business area has a
four-letter code, and that code is the start of every message identifier. Each message is described in a message
definition, which is also converted into a syntax message scheme such as an XML schema.

## Business areas

- pain: payments initiation, messages that support starting a payment from the ordering customer to a financial
  institution that services a cash account, and reporting its status.
- pacs: payments clearing and settlement, messages that support clearing and settlement between financial
  institutions.
- camt: cash management, messages that support reporting and advising on the cash side of financial
  transactions, including cash movements, balances, and exceptions and investigations.

## Message identifier structure

A message identifier has four parts: four letters for the business area, three digits for the message
definition, three digits for the variant and two digits for the version.

## Source note

This summary names three business areas as examples, and the repository lists more. It is based on the ISO 20022
site's message definitions page. That page blocked an automated fetch, so the details come from a search-engine
summary of it and should be checked against the page.
