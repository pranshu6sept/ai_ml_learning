# Week 7: Azure OpenAI, Foundry and AI Search, with infrastructure as code

Roadmap items: Azure OpenAI (deployments, quotas and tokens per minute, content filters, embeddings deployment); AI Foundry (project, prompt flow, evaluations, model catalogue); AI Search (indexers, skillsets, semantic ranker, vector profiles); **deliverable: infrastructure as code for these resources.**

This file records what was done and measured so far. Items not yet done are listed at the end, not implied.

## Status against the roadmap

| Item | Status |
|---|---|
| Azure OpenAI deployments, quotas, embeddings deployment | Done in Weeks 4-6 and extended: chat 50K tokens per minute, embeddings 10K, a separate judge model. See "Quota findings" |
| Azure OpenAI content filters | **Not done** (no configuration or test yet) |
| Foundry project | **Deployed** (`payments-rag`), no use made of it yet |
| Foundry prompt flow | **Skipped on purpose**: retired on 2027-04-20, not recommended for new work, hub projects only (Microsoft docs). The roadmap item is out of date |
| Foundry evaluations | Partly: the `azure-ai-evaluation` evaluators were run in Week 5 outside a project. Not yet run inside the Foundry project or portal |
| Foundry model catalogue | **Not done** |
| AI Search indexers and skillsets | **Done and measured** (below) |
| AI Search semantic ranker, vector profiles | Done in Week 4 |
| Deliverable: IaC for these resources | **Done**: `infra/main.bicep` (OpenAI, Search, roles, budget) and `infra/week7.bicep` (Storage, Foundry project, optional Basic Search) |

## Infrastructure as code

`infra/week7.bicep` is a separate template for a separate resource group (`rg-payments-rag-w7`), so Week 4-6 resources are untouched and Week 7 can be deleted in one step. It creates:

- a Storage account (Standard LRS) with a `corpus` container, shared-key access off (Entra roles only);
- a Foundry resource (kind `AIServices`) and a project, keyless (`disableLocalAuth`). The current Foundry model is an account plus a child project; no hub is needed;
- optionally, a Basic Azure AI Search service with a managed identity, and the role assignments that let it read the blobs and call the embedding model.

`what-if` showed 7 creates by default and 13 with the Basic service; the deployment succeeded (13 resources, about 9.5 minutes). One what-if line reads "Unsupported": the cross-resource-group OpenAI role assignment, whose principal ID only exists after the search service does.

## Indexer pipeline: Blob Storage to Azure AI Search

**Constraint found first:** Microsoft's documentation says an indexer can connect to Blob Storage with a managed identity only on **Basic tier or higher**. The free tier can't do keyless Blob indexing (it also caps indexer runs at 3 minutes and AI enrichment at 20 free transactions per indexer per day). So the demo ran on a temporary Basic service in Central India (list price 0.133 USD per hour), deleted after the measurement: it was up for about half an hour. The subscription is a free trial with the spending limit on, so usage draws on trial credit.

**What was built** (`payments_rag/blob_indexing.py`, `evals/run_blob_indexer.py`): cleaned documents uploaded to Blob Storage; a blob indexer that reads them as the search service's identity; a skillset with Text Split (pages of 600 characters, 100 overlap) and the Azure OpenAI embedding skill; index projections so each page becomes its own search document. No keys anywhere. The pipeline is rebuilt from code in about a minute.

**Run result:** 11 documents processed, 0 failed, 0 errors, 0 warnings, 35.9 s for a reset and full run (the first automatic run took 8 s). The index held 44 pages of 167 to 595 characters (median 553).

**Retrieval compared with our push pipeline** (`results/indexer_vs_push.md`; 69 answerable golden questions; all three use keyword + vector hybrid search with no semantic ranker, so only chunking and indexing differ):

| Index | Chunks | Hit@1 | Hit@3 | Recall@5 | MRR@10 | nDCG@5 |
|---|---|---|---|---|---|---|
| push, fixed chunks | 52 | 0.43 | 0.81 | 0.90 | 0.64 | 0.76 |
| push, structure-aware chunks | 63 | 0.62 | 0.84 | 0.91 | 0.75 | 0.77 |
| indexer (Text Split, 600 chars) | 44 | 0.57 | 0.88 | 0.95 | 0.72 | 0.81 |

Gold phrase intact inside one indexer page for 68 of 69 questions.

- **The managed indexer is competitive with our own pipeline.** It is ahead of fixed chunks on every measure and about level with structure-aware chunks: slightly lower Hit@1 (0.57 vs 0.62), slightly higher Hit@3, recall and nDCG. Those gaps are three or four questions in 69, so I would not call either ahead; one run, my own questions.
- **What it cannot do:** keep the heading path (`section`) or cut on document structure, so citations lose the section name. Text Split cuts by length. The richer alternative, the Document Layout skill, needs a Foundry Tools resource and was not tried.
- **Where each wins.** Push: full control of chunking and metadata (filters on region and date need extra fields mapped through the skillset), runs on the free tier, no storage account. Indexer: scheduled, incremental re-indexing of changed blobs, no chunking or upload code to run, but needs Basic or higher for keyless access.
- **Not measured:** incremental updates (changing one blob and re-running), scheduling, and cost at a scale beyond 11 documents.

## Quota findings

- **Rate limits are per deployment and bind before token limits:** the chat deployment allows 50 requests per minute at 50K tokens per minute. Paced for 150 and a run was throttled, with the SDK retrying silently so latency rose rather than errors appearing.
- **Quota tier:** the subscription is on the Free Tier and was due to auto-upgrade to Tier 1 from 2026-10-08. I set `tierUpgradePolicy` to `NoAutoUpgrade` on request; the first reads lagged the change, and a later read confirmed it.
- **Semantic ranker** beyond the free allowance is listed at 1.00 USD per 1,000 queries; the free tier's monthly allowance is not stated in the limits page I read.

## Open items

- [ ] Azure OpenAI content filters: see what the default filter does to a payments question, and configure one
- [ ] Foundry project: run evaluations in it, and try the model catalogue (a non-OpenAI model, subject to quota)
- [ ] Indexer: incremental update and schedule test
- [ ] Decide whether to keep the Foundry resource and storage account or tear Week 7 down (both cost almost nothing)
- [ ] Tick the roadmap box for prompt flow as "skipped, retired" rather than done
