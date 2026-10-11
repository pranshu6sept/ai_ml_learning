# Week 11: drift on the assistant's side

## 1. Do the questions drift? (real embeddings, read against a null)

Reference: the 48 development questions. AUC = how well a classifier tells the set from the reference (0.5: it cannot). **Null** = the same measurement between two random halves of the reference, where nothing has moved; a set is 'distinguishable' only if its AUC beats the null's 95th percentile. At most 24 rows per side, 20 draws.

| Question set | n | AUC | Null AUC (mean / 95th pct) | Distinguishable | Centroid cosine distance | Length PSI (set, same size) | Length PSI null 95th pct | Length distinguishable |
|---|---|---|---|---|---|---|---|---|
| heldout | 14 | 0.41 | 0.41 / 0.55 | **no** | 0.0960 | 2.21 | 3.68 | **no** |
| corpus_update | 6 | 0.43 | 0.35 / 0.47 | **no** | 0.1583 | 5.99 | 5.95 | **yes** |
| independent (web-sourced wording) | 44 | 0.58 | 0.48 / 0.64 | **no** | 0.0788 | 2.13 | 2.80 | **no** |
| abstain (off-topic) | 18 | 0.50 | 0.42 / 0.52 | **no** | 0.1471 | 1.80 | 3.24 | **no** |
| attacks (user channel) | 68 | 0.97 | 0.48 / 0.64 | **yes** | 0.4308 | 2.57 | 2.80 | **no** |
| compound attacks | 10 | 0.98 | 0.47 / 0.70 | **yes** | 0.3014 | 6.05 | 4.63 | **yes** |

## 2. Would we notice retrieval quality decaying? (a document removed from the index)

BM25 over structure-aware chunks; baseline Hit@3 = 0.725 on 69 answerable questions. Decay is flagged when Hit@3 falls by more than 0.043 (= 3 questions). The questions never change, so input drift is zero. The last two columns are the LABEL-FREE signal: how much the distribution of each question's best retrieval score moved.

| Document removed | Questions it answers | Hit@3 | Drop | Quality decay flagged | Best-score PSI | Best-score KS gap |
|---|---|---|---|---|---|---|
| faqs | 12 | 0.623 | +0.101 | **YES** | 0.133 | 0.101 |
| upi_overview | 9 | 0.638 | +0.087 | **YES** | 0.135 | 0.145 |
| iso20022_message_identifiers | 4 | 0.652 | +0.072 | **YES** | 0.062 | 0.101 |
| iso20022_overview | 6 | 0.652 | +0.072 | **YES** | 0.073 | 0.072 |
| card_scheme_public_summary | 14 | 0.667 | +0.058 | **YES** | 0.051 | 0.058 |
| cfpb_credit_card_disputes | 6 | 0.667 | +0.058 | **YES** | 0.123 | 0.101 |
| pci_dss_overview | 4 | 0.667 | +0.058 | **YES** | 0.107 | 0.072 |
| psd2_overview | 6 | 0.667 | +0.058 | **YES** | 0.064 | 0.101 |
| rbi_card_not_present_afa | 7 | 0.667 | +0.058 | **YES** | 0.070 | 0.087 |
| rbi_payment_systems_public_summary | 3 | 0.667 | +0.058 | **YES** | 0.044 | 0.072 |
| rbi_authentication_directions_2025 | 5 | 0.710 | +0.014 | **no** | 0.067 | 0.087 |
