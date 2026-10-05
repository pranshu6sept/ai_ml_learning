Lifecycle of the managed indexer on the Week 7 Basic search service (one run of the script; 11 documents, 44 pages at baseline).

| Step | Change | Documents the indexer processed | Pages in index | pages of faqs / card scheme / upi | Extra |
|---|---|---|---|---|---|
| 1 baseline (reset + full run) | 11 documents | 11 | 44 | 4 / 5 / 3 |  |
| 2 no change | none | 11 | 44 | 4 / 5 / 3 |  |
| 3 edit one blob | appended a sentence to faqs.md | 11 | 60 | 6 / 6 / 3 | marker_found_in=['faqs'] |
| 4 delete a blob (no detection policy) | deleted card_scheme_public_summary.md | 1 | 44 | 4 / 5 / 3 |  |
| 5 enable soft-delete detection, run | data source updated | 1 | 39 | 4 / 0 / 3 |  |
| 6 undelete the blob | restored card_scheme_public_summary.md | 0 | 39 | 4 / 0 / 3 |  |
| 7 scheduled run (every 5 minutes), no manual trigger | appended a sentence to upi_overview.md | 1 | 39 | 4 / 0 / 3 | marker_found_in=['upi_overview'], waited_s=302 |
