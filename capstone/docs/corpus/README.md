# Public payments corpus

This folder is the starting point for the RAG capstone's knowledge base. It contains only public,
non-confidential banking and payments material.

## Allowed sources

Use public, vendor-authored or regulator-published material only. Good examples include:

- ISO 20022 overview and message standards summaries
- card-scheme public rule summaries and FAQs
- RBI payment-system public guidance
- PSD2 and PCI-DSS public summaries
- author-written FAQs based on public material only

Do not add:

- employer internal documentation
- customer-specific data
- confidential implementation notes
- anything not available publicly or without permission

## Folder layout

- `raw/` — original downloaded or copied public docs (or their markdown summaries)
- `processed/` — cleaned versions ready for chunking and indexing
- `sources.json` — metadata for each source in the corpus
- `faqs.md` — a small set of starter FAQs written from public guidance

## Working rule

Every document in this corpus should be traceable to a public source and should include its title,
source, URL or publication reference, and a short note about why it is useful for the payments
assistant.
