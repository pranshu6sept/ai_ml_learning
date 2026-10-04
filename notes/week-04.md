# Phase 2: RAG + orchestration

## Week 4 · Oct 26–Nov 1 · RAG core

> ### Status: Week 4 is closed against the roadmap (4 Oct 2026)
>
> On 3 Oct I wrongly marked this week closed against a plan that mixed in Week 5 items and left out Week 4 items (semantic ranker,
> HNSW and filter concepts, the resume). Those are now done: see "Roadmap check" below. The resume item was done by the author; I
> have not seen the finished resume. Week 5 items done early are listed separately in the same table.
>
> **Delivered.** An 11-document public payments corpus with a validated registry and manifest; four chunking strategies; a
> retrieval stack (TF-IDF, BM25, stemming, local and Azure embeddings, hybrid search, cross-encoder reranker); Azure OpenAI
> (South India) and Azure AI Search (Central India) deployed from Bicep with keyless auth; a grounding rule with cited
> generation, citation enforcement and a quote-verified answerability check; and 130 evaluation questions across five
> files. 111 tests; CI green on `d6ee1e6`. All seven original plan items are done, with caveats written beside each.
>
> **Headline numbers, with their limits.** Azure hybrid retrieval, structure-aware chunks: Hit@3 0.91 on my dev questions
> but 0.67 on 44 questions from the web (Hit@5 1.00). Grounding on 80 questions: 53 of 55 answerable answered, 52 correct,
> no wrong answer shipped through the gate. The quote-verified check answers 45 of 55 where the reranker gate answers 31, but
> on the web questions the two were within noise (6 against 5 of 9). Every number comes from questions I wrote or labelled,
> a judge model that missed real errors, and small samples.
>
> **Gaps carried forward, not done:**
> 1. A question set written and labelled by someone who has not read the corpus (the biggest weakness).
> 2. The grounding, citation and answerability runs predate the final RBI annotations; repeating them takes about 40 minutes.
> 3. Four author-written documents are only partly verified; the ISO, Mastercard and NPCI pages could not be read; dates are
>    `null` for 7 of 11 documents.
> 4. Citation enforcement can drop the sentence that answers the question (h02); the rewrite retry is not measured at scale.
> 5. The retrieval misses behind q17 and q33; paraphrased questions are the weak spot; the BM25 and stemming gain did not
>    generalise to the web questions.
> 6. Not tried: a true embedding-based semantic chunker, a different checker model, a chunk-size test.
> 7. **The Azure resources are still deployed** (free Search tier; OpenAI bills per token only). `infra/teardown.ps1` removes
>    them, and `python -m payments_rag.ingestion --check-index` tells you whether the index matches the corpus.
>
> **What I would do differently.** Check a claim against the data before writing it down (the judge, the "caches committed"
> claim and the generation timing were all wrong at first); run the suite with the optional packages blocked before pushing
> (CI failed once because I did not); and record which corpus an index was built from the moment it is built.

### Roadmap check: what the roadmap asks for in Weeks 4 and 5

**Week 4 (roadmap):**

| Roadmap item | Status |
|---|---|
| Assemble the corpus (no confidential employer material) | **Done, with caveats:** 11 documents, 4 only partly verified; only you can confirm no employer content |
| Chunking: fixed, recursive, semantic, structure-aware | **Done** |
| Embeddings model choice; vector DB concepts (HNSW, filters) | **Done, with limits.** Two models compared on retrieval, and the rationale, HNSW, filters and the semantic ranker are written up in `week-04-fundamentals.md` section 11. Not done: recall against exact search, HNSW tuning, `text-embedding-3-large`. |
| Azure AI Search index with vector + keyword (hybrid) + semantic ranker | **Done and measured live.** Semantic ranker (`semantic=True`) compared with hybrid alone and with the local cross-encoder on all four question sets (`evals/rerankers_eval.md`): best Hit@1 and MRR on every set. Small n, my own questions, one run: see the reranker section. |
| Deliverable: ingest and retrieve working end to end against AI Search | **Done.** `python -m payments_rag.indexing` ran live (52/63/100/63 chunks per strategy) and records which corpus the index holds. `python -m payments_rag.ask "question"` is the plain retrieve -> generate path: hybrid + semantic ranker, quote-verified answerability check, cited answer or refusal. |
| Resume: start reframing | **Done by the author** (4 Oct 2026). I drafted a plan from the resume (kept local, git-ignored); I have not seen the final resume. |
| Write-up + push | **Done** |

**Week 5 (roadmap), partly done early inside this file:**

| Roadmap item | Status |
|---|---|
| Golden set of 50 to 100 questions with expected source chunks and reference answers | **Done in Week 5:** 95 questions with gold passages and reference answers (`golden_set.jsonl`); see `week-05.md` |
| Retrieval metrics: recall@k, MRR, nDCG | **Done in Week 5:** all three, in `results/retrieval.md` |
| Generation metrics: faithfulness/groundedness, answer relevance (RAGAS or Azure AI Foundry evaluators) | **Done with my own judge, not RAGAS/Foundry:** faithfulness, relevance, correctness vs reference (`results/generation.md`); see `week-05.md` |
| Compare the 4 chunking strategies with a results table | Done for retrieval; answer-level only for structure-aware chunks |
| Deliverable: `evals/` runnable with one command, results committed | **Done:** `run_all.py` (offline) and `run_all.py --azure` |
| Write-up + push | Partly: written up here, not as a separate Week 5 write-up |

### The question

How do I build a payments assistant that answers questions from public banking and payments docs
without hallucinating, without leaking private information, and with enough structure to retrieve the
right source before answering?

This is the first week of the capstone phase: move from model basics to grounded retrieval. The key
idea is that the model should answer from retrieved evidence, not from memory alone.

### Planned work

- [x] (11 documents, about 3,000 words after cleaning; 5 read from official pages, 2 known only through search summaries, 4 author-written and only partly verified because several sources block automated fetching: see "Round 2") Assemble the banking/payments corpus from public sources only: ISO 20022 guides, card-scheme
  rules summaries, RBI/PSD2/PCI-DSS public docs, and your own written FAQs based on public
  information.
- [x] (registry validation, cleaning, manifest and index-staleness check in `payments_rag/ingestion.py`; it cannot judge whether a document is confidential) Build a document ingestion pipeline that keeps clean source metadata and avoids confidential
  employer material.
- [x] Implement four chunking strategies: fixed-size, recursive, semantic, and structure-aware.
- [x] (retrieval quality for all four strategies; answer quality was measured for structure-aware chunks only) Compare the chunking strategies on retrieval quality and answer usefulness.
- [x] (TF-IDF, BM25, local and Azure embeddings, hybrid search and a reranker) Add a retrieval pipeline that indexes chunks and keeps source references for each answer.
- [x] (evidence, abstain rule, cited prompt and generation with gpt-4.1-mini on Azure, all built, tested and measured) Define a simple grounding rule: every answer must cite evidence from retrieved passages.
- [x] (retrieval, groundedness and latency all measured; judge-based groundedness is imperfect) Write an evaluation plan for retrieval quality, answer groundedness, and latency.

### Why this matters

The hardest part of a domain assistant is not writing a plugin or a prompt. It is making sure the
model sees the right evidence in the right format. Poor chunking can break retrieval even when the
embedding model is good. A chunk that is too big mixes concepts; a chunk that is too small loses
context; a chunk built without structure misses the relationship between rules, examples, and
exceptions.

This week is about building the evidence layer that every later orchestration step depends on.

### Week 4 implementation plan

#### 1. Corpus setup

- [x] Create a public-only payments corpus under the capstone source directory.
- [x] (publication date is `null` for 7 of 11 documents: the sources show none) Include source metadata: title, source type, publication date, URL, jurisdiction, and notes.
- [x] Start with a small but realistic set of documents:
  - ISO 20022 overview and message examples
  - card-network rules summaries (e.g. authorization, settlement, dispute basics)
  - RBI / PSD2 / PCI-DSS public guidance summaries
  - 5–10 FAQ pages written from public documentation in your own words
- [ ] (the corpus README states the rule and every source is a public page or author-written, but only you can confirm no employer-specific content) Keep every document clearly labelled as public material only and remove any confidential or employer-specific content.

#### 2. Chunking implementation

- [x] Build a shared chunking interface with a `chunk_text()` function for each strategy.
- [x] Implement fixed-size chunking first as the baseline.
- [x] Implement recursive chunking using heading and paragraph boundaries.
- [x] (keyword-topic overlap, not embeddings yet) Implement semantic chunking with a similarity-based merge strategy.
- [x] Implement structure-aware chunking by preserving headings, bullet points, and table context.
- [x] (no page numbers: the sources are markdown) Attach metadata to each chunk: document ID, section heading, page/source, chunk index, and source URL.

#### 3. Retrieval and indexing

- [x] (TF-IDF vectors) Build a lightweight vector index for each chunking strategy.
- [x] Store both the chunk text and the metadata in the index.
- [x] Make retrieval return the top-k candidate chunks with source references.
- [x] (the prompt forces citations and the model is called on Azure, but only 78% of sentences carry one) Keep the answer path grounded: the model should explain which source it used.
- [x] Test retrieval on a small bank of sample questions before building the full app flow.

#### 4. Evaluation plan

- [x] (27: 15 direct, 9 paraphrased, 3 unanswerable) Create a mini evaluation set with 20–30 domain questions.
- [x] Check retrieval quality by whether the correct source chunk is present in the top results.
- [x] (a judge model plus my own reading of the flagged answers) Check groundedness by verifying that the answer cites evidence from retrieved content.
- [x] Track latency for indexing and retrieval on a small set of queries.
- [x] Record qualitative failures: missing section context, weak chunk boundaries, and poor retrieval rankings.

### Chunking strategy to implement

1. Fixed-size chunking
   - simple and fast
   - easy to debug
   - often fails when a rule spans multiple sections or when context boundaries are important

2. Recursive chunking
   - splits by headings and paragraph boundaries first, then falls back to smaller chunks
   - better for prose-heavy docs with natural structure

3. Semantic chunking
   - groups related ideas by meaning rather than fixed token counts
   - useful for long policy documents and FAQs that discuss related concepts together

4. Structure-aware chunking
   - respect document structure such as headings, tables, bullets, and section hierarchies
   - usually the best choice for standards and policy docs where context matters

### Results (43 answerable questions, 5 unanswerable; `capstone/evals/evaluate_chunking.py`)

The corpus is 10 documents (about 2,400 words). A question counts as answered only if a top-k chunk comes
from the expected document **and** contains the exact gold phrase that answers it. A test checks that every
gold phrase exists in its document. Chunks target about 80 words; retrieval is TF-IDF over all documents.
**One question is worth 0.023 of any score.** Of the 43, 28 are direct and 15 are paraphrased.

Meta sections ("Practical RAG relevance", "Example questions this helps answer") removed at ingestion:

| Strategy | Chunks | Hit@1 | Hit@3 | Hit@5 | MRR@10 | Hit@3 direct | Hit@3 paraphrased |
|---|---|---|---|---|---|---|---|
| fixed | 39 | 0.44 | **0.72** | **0.88** | **0.62** | 0.71 | **0.73** |
| recursive | 48 | 0.42 | 0.65 | 0.79 | 0.57 | 0.71 | 0.53 |
| semantic (keyword topics) | 78 | 0.30 | 0.58 | 0.70 | 0.47 | 0.61 | 0.53 |
| structure_aware | 48 | **0.49** | **0.72** | 0.86 | **0.63** | **0.82** | 0.53 |

What it shows, and what it doesn't:

1. **No strategy clearly wins.** Fixed and structure-aware tie at Hit@3 (0.72). Structure-aware leads at
   Hit@1 (0.49 vs 0.44, two questions) and on direct questions (0.82 vs 0.71); fixed leads on paraphrased
   ones (0.73 vs 0.53). Each gets right questions the other misses.
2. **My earlier hint did not replicate.** On the 4-document corpus, structure-aware had Hit@1 0.71 against
   0.58 for fixed. With 10 documents and 43 questions the gap shrank to 0.49 against 0.44. A three-question
   difference on 24 questions was mostly noise, which is exactly what the notes warned.
3. **Semantic chunking is clearly worst** (Hit@1 0.30, Hit@3 0.58). It makes the most chunks (78), some of
   only 6 words, because a keyword-topic list splits sentences it doesn't recognise. That gap (five to eight
   questions) is large enough to trust.
4. **The harder corpus exposed what the small one hid.** Hit@3 fell from 0.96 to about 0.72 for the best
   strategies. More documents means more near-duplicates and distractors (three documents discuss disputes,
   several discuss authentication), and the new questions ask for specific facts.
5. **Five questions fail in every strategy, so chunking is not the problem there.** They are vocabulary
   mismatches: "Can shops charge extra for paying by card?" vs "bans retailer surcharges"; "simplified
   option" vs "relaxation"; "Who does PCI DSS apply to?" vs "applies" (no stemming); "What does pacs mean?"
   where a short chunk full of "ISO 20022" outscores the long chunk that contains "pacs"; and a money-movement
   paraphrase. These need embeddings or a hybrid (keyword plus vector) search, not better chunks.
6. **Paraphrased questions favour longer chunks here.** Fixed 80-word windows score 0.73 vs 0.53 for the
   smaller structure-aware chunks. My guess is that a longer chunk contains more words that can overlap with
   a differently worded question. That is a **hypothesis I haven't tested**.
7. **TF-IDF scores can't tell answerable from unanswerable, and the gap grew.** The top score for the 5
   unanswerable questions (0.34 to 0.42) is now *higher* than for answerable ones (0.32 to 0.39). They are
   about topics that exist in the corpus (PCI DSS, UPI), so they share many words with real chunks. A
   similarity threshold can't implement "abstain".
8. **Removing meta sections now matters little** (Hit@1: fixed +0.04, semantic +0.02, recursive -0.02,
   structure-aware 0.00). It helped every strategy on the tiny corpus; at this size the effect is within noise.
   I still strip them, because a chunk that lists a question is not evidence.
9. **No gold phrase was ever cut by a chunk boundary** (intact rate 1.00 everywhere), so the usual argument
   against fixed-size cutting still isn't demonstrated. The documents are short and paragraph-based.

**Caveats on this evaluation:** the six new documents and their questions were written together, and the
direct questions use wording close to the summaries, so the **paraphrased questions are the fairer test**. The
gold phrases come from the summaries, not from the original pages. Two sources (UPI and the ISO 20022 identifiers)
could not be fetched and rest on search-engine summaries of the official pages; four of the ten documents are
still author-written and unchecked. `sources.json` records this in a `verification` field.

### BM25 and stemming (`capstone/evals/evaluate_retrievers.py`)

Two cheap retrieval fixes tried before embeddings. **BM25** replaces TF-IDF's scoring (it saturates repeated
words and corrects for chunk length). **Stemming** (Snowball English) reduces "applies" and "apply" to the same
stem. BM25 uses its standard defaults (k1 = 1.5, b = 0.75); nothing was tuned.

Because I chose stemming *after* seeing which questions failed, I wrote **12 held-out questions before changing
any retrieval code** and scored them without changing anything afterwards.

Hit@3, structure-aware chunks, meta sections removed:

| Retrieval | Dev set (43 questions) | Held-out set (12 questions) |
|---|---|---|
| TF-IDF (before) | 0.72 | 0.83 |
| TF-IDF + stemming | 0.79 | 0.75 |
| BM25 | 0.74 | 0.83 |
| BM25 + stemming | **0.81** | 0.83 |

On the dev set, Hit@5 rose from 0.86 to 0.98 and paraphrased-question Hit@3 from 0.53 to 0.80 with TF-IDF plus
stemming. BM25 + stemming with structure-aware chunks recovered 3 of the 5 questions every strategy had missed
(q25 "apply" vs "applies", q33, q41 "pacs"). q30 ("charge extra for paying by card" vs "bans retailer
surcharges") was never recovered by any configuration, and q19 only by TF-IDF + stemming: no stemmer links words
that differ in wording rather than form.

What it shows, and what it doesn't:

1. **The dev gains did not show up on held-out questions.** Held-out Hit@3 stayed at 0.83 (BM25 + stemming) or
   even fell to 0.75 (TF-IDF + stemming), a one-question difference (one question = 0.083). So the dev
   improvement is **plausible but unproven**, and partly the result of fitting fixes to the questions I'd looked at.
2. **The held-out set is too small and too easy to settle it.** Twelve questions can't detect a 0.05 to 0.09
   change, and plain TF-IDF already scored 0.83. It also contradicted dev on chunking: the semantic strategy
   was best at Hit@1 there (0.75) and worst on dev (0.30). That swing is what noise at n = 12 looks like.
3. **BM25 alone barely moved anything** (dev Hit@3 +0.02 to +0.05). On passages this short and uniform in size,
   length normalisation has little to correct.
4. **Stemming makes abstaining harder.** The top score for unanswerable questions, relative to answerable ones,
   rose from 1.14 (TF-IDF) to 1.23 (TF-IDF + stemming) and 1.31 (BM25 + stemming): stemming lets more words match,
   including for questions the corpus can't answer.
5. **My decision:** `Retriever(method="bm25", stem=True)` is available and probably helps a little, but the
   defaults stay TF-IDF without stemming so earlier numbers still reproduce. The vocabulary-mismatch failures
   (q30 and the paraphrases) need meaning-based matching, so embeddings are the next step. A bigger
   held-out set, written by someone who hasn't seen the documents, would make the next comparison conclusive.

### Embeddings and hybrid search (`capstone/evals/evaluate_embeddings.py`)

Run locally with an open-source model (all-MiniLM-L6-v2, 384 numbers per text, no API key). **Hybrid** fuses the
BM25 + stemming ranking with the embedding ranking by reciprocal rank fusion (constant 60). The model and the
fusion constant were fixed before looking at results; nothing was tuned. Same dev (43) and held-out (12) questions.

Structure-aware chunks, meta sections removed:

| Retrieval | Dev Hit@1 | Dev Hit@3 | Dev Hit@5 | Dev MRR | Held-out Hit@3 | Held-out Hit@5 |
|---|---|---|---|---|---|---|
| TF-IDF | 0.49 | 0.72 | 0.86 | 0.63 | 0.83 | 0.83 |
| BM25 + stemming | 0.53 | 0.81 | 0.95 | 0.69 | 0.83 | 0.83 |
| Embeddings | 0.56 | 0.88 | 0.95 | 0.72 | 0.92 | 0.92 |
| **Hybrid** | **0.60** | **0.95** | **0.98** | **0.77** | 0.92 | **1.00** |

What it shows, and what it doesn't:

1. **This is the first clear gain.** On the dev set, hybrid lifts Hit@3 from 0.72 to 0.95, ten questions out of 43
   (one question is worth 0.023), well above noise. On the held-out set it goes 0.83 to 0.92 at Hit@3 and 0.83 to
   1.00 at Hit@5, one and two questions. The direction agrees, but 12 questions can't confirm the size.
2. **Hybrid recovers all 5 questions every earlier method missed.** Embeddings alone got q19, q25 and q30. q30
   ("Can shops charge extra for paying by card?" vs "bans retailer surcharges") is the one lexical search never
   could. BM25 + stemming got q25, q33 and q41 ("pacs", a rare exact token). The two make **different mistakes**,
   so combining them covers both: meaning for paraphrases, exact tokens for names and codes.
3. **Chunking matters again once retrieval is semantic.** With embeddings, structure-aware chunks reach dev Hit@3 0.88
   against 0.72 (fixed), 0.70 (recursive) and 0.63 (semantic), and 0.92 vs 0.75 on held-out. My guess is that the
   heading path on each chunk gives its vector the topic context. That is a **hypothesis I haven't tested**.
4. **Hybrid helps the top few results, not necessarily the first.** Held-out Hit@1 was 0.58 for hybrid against 0.67 for
   TF-IDF. That's fine if a language model reads the top 3 to 5 chunks, and worth checking if only the top 1 is used.
5. **Abstaining is still unsolved.** Can the top score separate answerable from unanswerable questions? AUROC
   (1.0 perfect, 0.5 chance): TF-IDF 0.48, BM25 + stemming 0.45, embeddings 0.57, hybrid 0.53. With only 7 unanswerable
   questions the uncertainty is wide, but nothing suggests the score works. The grounding rule needs a different
   signal: a reranker that reads question and chunk together, or a model check that the evidence answers the question.
6. **Cost:** an embedding query takes about 8 ms on a CPU (hybrid about 10 ms) against 0.4 ms for BM25, plus a
   model to download and load. Still small next to a language-model call.

**Caveats:** the corpus is about 40 to 50 chunks, so the top 5 covers roughly a tenth of the index; the held-out set
is 12 questions; I tried one local model, not Azure OpenAI embeddings; and I wrote the documents and the questions.
The model reads at most about 256 word pieces, so chunks must stay short. **Working choice for the capstone:
structure-aware chunks with hybrid retrieval.** The `Retriever` defaults stay TF-IDF so older numbers reproduce.

### Reranking and the grounding rule (`capstone/evals/evaluate_abstention.py`)

**The rule** (`payments_rag/grounding.py`): retrieve 10 candidates with hybrid search, rerank them with a
cross-encoder, and hand a language model the top 3 passages **only if the best one scores above a threshold**;
otherwise abstain and pass on no evidence at all. `build_prompt` tells the model to answer only from the numbered
passages, cite them like [1], and otherwise say "I don't know based on the provided documents." There is no
generation step yet (that needs Azure OpenAI), so what's measured is the retrieval half of grounding.

A **cross-encoder** reads the question and a chunk *together* and scores the pair, which is slower than comparing
stored vectors but more accurate, so it is used only on the 10 candidates.

I wrote 18 more unanswerable questions before running anything (14 close to real topics, such as "What are the
twelve PCI DSS requirements?", and 4 off-topic). The threshold is chosen on a **tune set** (the 43 dev questions
and 9 of the new ones) and judged on a **test set** (the 12 held-out and the other 9). Structure-aware chunks.

How well does each score separate answerable from unanswerable questions (AUROC, 1.0 perfect, 0.5 chance)?

| Signal | Tune | Test | All | All, hard questions only |
|---|---|---|---|---|
| BM25 | 0.48 | 0.80 | 0.58 | 0.50 |
| Embedding similarity | 0.62 | 0.77 | 0.68 | 0.62 |
| Hybrid score | 0.53 | 0.64 | 0.56 | 0.47 |
| **Cross-encoder reranker** | **0.78** | **0.80** | **0.79** | **0.75** |

What it shows, and what it doesn't:

1. **The reranker is the first useful abstain signal**, and the retrieval scores aren't (hybrid is at chance on hard
   questions). It still isn't a clean separator: 0.79 means a typical answerable question outscores a typical
   unanswerable one about four times in five.
2. **Reranking also puts the right chunk first more often:** dev Hit@1 0.60 to 0.74, held-out 0.58 to 0.67, and
   held-out Hit@3 0.92 to 1.00. The dev gain is six questions of 43; the held-out gains are one question each.
3. **The tuned threshold is safe but too cautious.** Applied to the test set it refused all 11 unanswerable
   questions (9 of 9 hard, 2 of 2 off-topic), so **no wrong answers**, but it also refused **7 of 12 answerable
   ones**. Balanced accuracy was 0.71.
4. **The threshold didn't transfer.** The tune set is mostly direct questions (28 of 43) and the test set mostly
   paraphrases (9 of 12), which score lower with a reranker trained on web search. So a cut-off chosen on one
   mix of questions is too strict for another. Calibrate on questions that look like real users' questions.
5. **It's a trade-off, not a single number.** Pooled over all questions: refusing 100% of unanswerable ones means
   answering only 42% of answerable ones; refusing 90% means answering 60%. The right point depends on costs: for a
   payments assistant a wrong answer probably costs more than a refusal, which argues for a strict threshold plus a
   graceful fallback (show the sources, or ask the user to rephrase) rather than a flat "I don't know".
6. **Next signal to try:** a language model that reads the passages and judges whether they answer the question
   (Azure OpenAI), which can handle paraphrases better than a score cut-off.

**Caveats:** 55 answerable vs 25 unanswerable questions in total, all written by me; the test set has only 2
off-topic questions; one reranker model (ms-marco-MiniLM, trained for web search, not for payments); the threshold
rule (balanced accuracy) treats both errors as equally bad, which isn't realistic.

### Azure setup, deployed and verified (`infra/`, `capstone/src/payments_rag/azure_clients.py`)

Deployed on 2 Oct 2026 from `infra/main.bicep`: Azure OpenAI (`text-embedding-3-small`, `gpt-4.1-mini`) in South India
and Azure AI Search (free tier) in Central India, keyless (Entra ID, no API keys). The first deployment succeeded, and
the smoke test passed every step on live Azure: sign-in, a 1,536-number embedding, index creation, upload of 213
chunks, hybrid search, and a cited answer from `gpt-4.1-mini`. Guide: [infra/README.md](../infra/README.md).

What the documentation and the account itself told me:

1. **Central India has no Azure OpenAI models** on the official region table; South India lists the embedding models
   and `gpt-4.1-mini`. Azure AI Search is the reverse (full features in Central India), so the two services are in
   different regions.
2. **Keyless works on every Search tier,** including free, but role-based access is **off by default**, so the template
   switches it on. Azure OpenAI has key authentication turned off, and my user holds the roles instead.
3. **Free search tier:** one service per subscription, 3 indexes, 50 MB, may be deleted if idle. One index holds all
   four chunking strategies (a `strategy` field filters).
4. **The "free trials have zero OpenAI quota" warning did not apply.** I asked Azure directly
   (`az cognitiveservices usage list --location southindia`): this `FreeTrial` subscription, spending limit on, has
   quota for `text-embedding-3-small` (1,000) and `gpt-4.1-mini` (200). Many other models show 0, and only one Azure
   OpenAI account is allowed. Check the real quota before trusting a warning.

Small things the real run caught: a hidden byte-order mark that Windows PowerShell 5.1 puts in the `.env` file (the
reader handles it); and a terminal opened before the CLI was installed cannot see `az`, so sign-in fails until it is
reopened.

**Azure vs the local hybrid, same questions and chunks** (`capstone/evals/azure_eval.md`, structure-aware chunks):

| | Dev Hit@1 | Dev Hit@3 | Dev Hit@5 | Dev MRR | Held-out Hit@3 | Held-out Hit@5 | Mean query time |
|---|---|---|---|---|---|---|---|
| Local hybrid (MiniLM + BM25, stemming) | 0.60 | 0.95 | 0.98 | 0.77 | 0.92 | 1.00 | about 10 ms |
| **Azure** (`text-embedding-3-small` + Search) | **0.74** | 0.93 | 0.93 | **0.84** | 0.92 | 1.00 | **about 400 ms** |

- **Azure ranks the right chunk first more often** (dev Hit@1 0.60 to 0.74, MRR 0.77 to 0.84), plausibly from the stronger
  embedding model. It does **not** find more answers in the top 3 or 5 (Hit@5 0.93 vs 0.98 is two questions), and the
  held-out set is level. So: better ordering, not better recall, on this small corpus.
- **With a better embedding model, chunking matters less:** on Azure the semantic strategy is no longer the worst, and
  all four are within 0.07 at dev Hit@3 (structure-aware leads at 0.93). My earlier "structure-aware helps" guess is
  weaker here.
- **Latency is the real cost.** About 400 ms per query against 10 ms locally, because each query makes two network
  calls (an embedding in South India, then the search in Central India) from this laptop. This is measured; it
  supports the Week 3 latency point and means the retrieval step is no longer negligible next to the model call.
- **Azure's hybrid scores are rank-fusion values** (about 0.03, near-ties), so they cannot serve as an abstain
  signal, the same finding as before. The reranker and grounding rule are still needed on top.
- **Caveats:** the same 55 small questions I wrote; one run; Azure's keyword side has no stemming; semantic ranker
  (available in Central India) not tried and might improve the ordering.

### Groundedness, end to end on Azure (`capstone/evals/evaluate_grounding.py`)

All 80 questions through the whole chain: Azure hybrid search (10 candidates), the local reranker, the top 3 passages,
`gpt-4.1-mini` with the cited prompt. A judge (the same deployment) then checks each answer against its passages. Two
operating points come from the same generations: **no gate** (always answer, so we see whether the model refuses on its
own) and **gated** (refuse when the best reranked score is below 4.41, a threshold chosen on the tune set only).

**No gate**

| | Result |
|---|---|
| Answerable (55): model answered / refused | 53 / 2 |
| Answerable answers judged correct | 52 of 53 |
| Unanswerable (25): model refused on its own / answered | **23** / 2 |
| Answers judged fully supported by their passages (judge; unreliable, see point 3) | 53 of 55 |
| Answers with at least one citation / every [n] a valid passage | 55 of 55 / 55 of 55 |
| **Sentences that carry a citation** | **76 of 98 (78%)** |
| Retrieved passages contained the answer (answerable) | 53 of 55 |
| Correct when they did and the model answered | 52 of 52 |

**Gated** (threshold 4.41): answerable answered 31 of 55, all correct; **24 answerable refused**; unanswerable refused 25
of 25, so **0 wrong answers shipped**. On the test half (threshold not fitted there): answered 5 of 12 answerable,
refused all 11 unanswerable.

What it shows, and what it doesn't:

1. **When the evidence contains the answer, the model uses it correctly (52 of 52).** The weak link is retrieval: the
   two answerable questions that lacked the answer in the top 3 (q17, q33) were the failures. A fix for answer quality
   starts with finding the right passage.
2. **The prompt makes the model abstain well on its own.** It refused 23 of 25 unanswerable questions, including ones
   whose passages were on topic. That is the cited prompt doing real work.
3. **The two unanswerable questions it did answer are subtle, and the judge is unreliable on them.** I read them:
   - u03 ("which message type for a customer credit transfer?") answered "pain", from a passage saying `pain` covers
     payment initiation. `pain` is a business area, not a message type, and the corpus never names the message, so this
     is a grounding failure: an answer built from a nearby passage.
   - b03 ("what is the maximum customer liability amount?") answered with the ₹2,000 transaction limit and "disclosed
     at enrolment". The passage never gives a liability amount; the answer mixes up two different things while using
     only words from the passage.
   **In the latest run the judge called both "supported".** Its verdicts changed between two runs of the same script:
   an earlier run flagged u03 (that run's output was overwritten, so I can't say more), the latest did not. By my
   reading the genuine problems are q17, u03 and b03 (3 of 55). The judge's latest flags were q17 and q31, and q31 is a
   false positive (its "political agreement" claim is in the passage). So it caught 1 of 3 real problems and raised 1
   false alarm: treat its 96% as an upper bound, and don't use a model to grade its own answers without reading them.
4. **The gate is an expensive extra guard.** It catches both bad answers (they scored 4.40 and 2.87) but only at a threshold
   of 4.41, which also refuses 22 answerable questions the model had answered, 21 of them correctly, mostly paraphrases.
   Lower thresholds keep more answers but let a hallucination through (at 3.0: 33 answered, u03 shipped; at 0: 47 answered,
   both shipped). The reranker score can't separate these cleanly because the two bad answers score like good ones.
5. **22% of sentences have no citation.** The prompt says to cite every claim, but the model often cites only the last
   sentence, or leaves a restating opening sentence uncited. The judge rated citations 98% correct, but it is lenient on
   missing ones. Citation coverage needs enforcing (a stricter prompt, or code that drops uncited sentences).
6. **Timing (this laptop to Azure), corrected on the rerun:** retrieval median 0.49 s (an embedding call and a search in two
   regions), rerank 0.12 s on the CPU, and generation **median 1.0 s (p90 1.6 s, max 4.7 s)**, measured in a run with no
   rate-limit waits. The earlier figures (median 4.9 s, mean 7.8 s, max 82 s) were inflated by retry waits: I had called the
   median "close to model speed", and it was not.

**Caveats:** my 80 questions, results from one complete run (a second run's judge verdicts differed), and a judge that is
the same model as the generator and demonstrably missed real errors. The model's own refusal and the gate were not tested against questions written by other people.

### Corpus verification: one document was presenting a repealed rule (`capstone/docs/corpus/`)

I tried to check the four author-written documents (and the two that rested on search summaries) against the real
sources, and the most useful result was a correction, not a confirmation.

**The RBI card-not-present circular of 6 Dec 2016 is repealed.** The RBI's Authentication Directions, 2025 (issued 25 Sep
2025, compliance by 1 Apr 2026) list it as item 8 of Annexure 2 (DPSS.CO.PD No.1431/02.14.003/2016-17), among eight
circulars from 2009 to 2016 that they repeal. My corpus had carried its ₹2,000 relaxation as if it were current, with only a
hedge ("later directions exist"). Fixed:

- The 2016 document is now titled "(2016, repealed)", opens with a status note, and states that it no longer applies.
  `sources.json` marks it `repealed` with `superseded_by`, and a test fails if a repealed document does not say so.
- A new document summarises the 2025 Directions (fetched; two-factor rule, dynamic factor, seven exemption categories,
  issuer compensation duty, cross-border card-not-present dates, the repeal list). Six questions about it are in
  `questions_corpus_update.json` (not scored yet).

What the other checks found (each source is marked in `sources.json`):

| Document | Result |
|---|---|
| ISO 20022 overview | Consistent with search summaries of BIS and Federal Reserve pages (common language, richer structured data). The ISO site returns 403, so it was never read there. The list of users is unconfirmed. |
| Card-scheme summary | Lifecycle and roles consistent with search summaries of Mastercard pages. The Mastercard PDF returned 403. Visa not checked. |
| RBI payment-systems summary | **Still unverified.** Generic, and the RBI Payments Vision page returned a CAPTCHA. Only the authentication and fraud-control themes are supported (by the 2025 Directions). Prefer the new document. |
| FAQs | Cross-checked against the other corpus documents only, which is not an independent source. FAQ 5's "non-receipt" is supported by nothing I fetched, and FAQ 6 is about this RAG system, not payments. |
| UPI, ISO identifiers | Still search summaries only (the NPCI page returned no content, the ISO page 403). |

**Publication dates:** every `sources.json` entry now has a `published` field, set to an explicit `null` where I don't know
it (a test enforces the field and the date format). Known: RBI 2016-12-06, RBI 2025-09-25, the EU PSD2 page 2025-11-27.
The other eight are `null`.

**Checks and what they did not cover:** local TF-IDF retrieval on the original questions barely moved with the extra
document (fixed-size Hit@3 0.72 to 0.77, the others unchanged), so it is not adding much confusion.

**Azure index rebuilt (3 Oct 2026).** The live index had kept the old, unlabelled 2016 text and lacked the new document, so
Azure would have stated the repealed ₹2,000 rule as current. I added `AzureSearchStore.recreate_index()` (delete, then
create empty, because an upload is an upsert and leaves stale chunks) and re-uploaded the 11-document corpus. Results:

- **The fix works where it matters.** Asked "Can I use the simplified online card payment option for amounts up to 2,000
  rupees?", the system now answers no, because the circular that allowed it was repealed, citing the repealed document and the
  2025 Directions. (It says "repealed in 2025"; the corpus only says the 25 Sep 2025 Directions repeal it with compliance by
  1 Apr 2026, so the effective date is looser than that answer implies.)
- **The old questions moved a little,** mostly by one or two questions, which is the noise level: structure-aware dev Hit@3
  0.93 to 0.88, Hit@1 0.74 to 0.70, held-out Hit@3 0.92 to 0.83 (one question of 12). A plausible cause is the extra RBI
  document, which overlaps in topic with the 2016 one. I did not test that.
- **The new questions retrieve poorly: 2 of 5 in the top 3 on every strategy** (fixed-size and structure-aware reach 3 of 5
  by rank 5). The two direct ones are found; the three **paraphrased** ones are not, because the 2016 circular, which covers
  the same topic, outranks the 2025 directions. Five questions can't support more than that, and I wrote them together with
  the document.
- **Reran grounding, citations and answerability on the rebuilt index** (cleared caches, same 80 questions; the 6 new RBI
  questions are not in these runs). The outcomes held:

| | Before the rebuild | After the rebuild |
|---|---|---|
| Grounding: tuned gate threshold | 4.41 | 4.41 |
| Model answered / correct (answerable) | 53 of 55 / 52 | 53 of 55 / 52 |
| Unanswerable refused by the model itself | 23 of 25 | 23 of 25 |
| Wrong answers shipped by gate and model | 0 | 0 |
| Sentences carrying a citation (default prompt) | 76 of 98 (78%) | 76 of 99 (77%) |
| Strict prompt, before enforcement | 137 of 140 (98%) | 135 of 141 (96%) |
| Sentences enforcement dropped | 3 in 3 answers | 6 in 5 answers |
| Answerability check: answerable answered | 44 of 55 | 45 of 55 |
| Answerability check: unanswerable shipped / fabricated quotes | 0 of 25 / 0 | 0 of 25 / 0 |
| Answerability AUROC: reranker / label / quote-verified | 0.79 / 0.96 / 0.90 | 0.79 / 0.97 / 0.91 |

  The evidence changed for 12 or more questions and two questions swapped between answered and refused (q18, q22, one each
  way), but the totals did not move. Only 2 of 80 answerability labels changed (h07 partial to full, hu2 partial to none), and
  one gate decision (h07). So the answerability check is stable across runs and across a changed index.

### Enforcing citations on every sentence (`capstone/evals/evaluate_citations.py`)

The grounding run found that 22% of sentences had no citation. I re-answered the 55 questions the model had answered
(same index, retrieval and top 3 passages) with a stricter prompt ("end EVERY sentence with a citation") and then
removed any sentence still without a valid citation (`enforce_citations`).

| Reply | Sentences with a citation |
|---|---|
| Baseline (default prompt) | 76 of 98 (78%) |
| Strict prompt, before enforcement | 137 of 140 (98%) |
| After enforcement | 137 of 137 (100%, by construction) |

What it shows, and what it doesn't:

1. **The prompt does almost all of the work.** 78% to 98% from one added instruction. Enforcement only handled the last 3
   sentences, in 3 answers, and no answer became a refusal. Mean length stayed at 37 to 38 words.
2. **The sentences enforcement dropped were the direct answers.** In q30, q41 and h11 the model wrote a lead sentence
   ("No, shops cannot charge extra...", "Pacs means payments clearing and settlement...", "No, you do not need to
   register...") and left it uncited, while citing the supporting detail. Dropping them leaves q30 without its "No" and q41
   starting with a dangling "It". As a safety net, drop-only is a bad trade for exactly the cases where it fires.
3. **So I changed the policy** (`generate_cited`): if a sentence lacks a citation, ask the model once to rewrite with a
   citation on every sentence including the first, and drop only what is still uncited. A first version accepted any rewrite
   that dropped no more sentences than before. **Trying it live on the three affected questions showed that was too weak:**
   h11 was fixed (the rewrite cited everything); q41 needed no retry at all (the model cited every sentence that time, so the
   "3 dropped sentences" are not a fixed number: they vary from call to call); and q30 got worse (the rewrite still lost
   its "No" lead, added an extra sentence and began with a dangling "This is because..."). The rule is now that a rewrite is
   used only if it is **strictly better** (fewer dropped sentences, not a refusal), with a unit test for the tie case. That
   fix was tested with a scripted fake model; only the first version was run on Azure.
4. **Presence is not correctness.** A sentence can cite a passage that does not support it. Enforcement guarantees the
   marker exists and points at a passage that exists; it does not check support.
5. **The judge disagreed with itself again.** On the first run it called u03 unsupported (the run before: supported) and
   flagged q31 as incorrect (a false alarm, as before). Its "51 of 53 correct" against the baseline's 52 was noise there.
6. **The rerun showed enforcement can really break an answer.** It dropped 6 sentences in 5 answers, and 4 of the 6 were again
   the answer's first sentence (7 of 9 across the two runs). For h02 ("What kinds of firms did the EU payments directive allow
   besides banks?") it dropped the only sentence that answered the question ("allowed a new category of payment service
   provider beyond banks") and kept the follow-on remark ("This increased competition and choice for consumers [2]"). The
   judge's new "incorrect" flag on h02 is right, so this run's 50 of 53 includes one real regression caused by enforcement.
   The rewrite retry was designed for exactly this case, but I have not measured it across all questions on Azure.
7. **A dropped hedge is not always a loss.** For b03 enforcement dropped "the exact maximum customer liability amount is not
   provided in the passages", but the answer's first sentence already said the amount "is not specified in the passages". It
   also shows a metric flaw: the grounding table counts only an exact "I don't know" as a refusal, so a correct hedge like
   this one is scored as the model answering an unanswerable question.
8. By my reading the only real failure among the answerable questions in the baseline is still q17 (the passages lacked the
   answer and the model answered anyway); with enforcement, h02 is a second, caused by dropping.

### A better abstain signal: ask for a quote, then check it (`capstone/evals/evaluate_answerability.py`)

The reranker score separated answerable from unanswerable questions only moderately (AUROC 0.79) and, to keep the bad
answers out, the gate refused 24 of 55 answerable questions. The new check asks the model whether the top 3 passages state
the specific fact the question asks for (`full`, `partial` or `none`) and, if `full`, to copy one sentence that does. **Code
then verifies that the quote really appears word for word in a passage**, so the model can't just claim an answer exists.
The question is answered only if the label is `full` and the quote is found. It needs no tuned threshold.

| Signal (all 80 questions) | AUROC | Gate alone: answerable answered | Gate alone: wrongly refused | Unanswerable shipped by the gate alone |
|---|---|---|---|---|
| Reranker score (threshold 4.41) | 0.79 | 31 of 55 | 24 | 1 (a04) |
| **Label `full` and quote verified** | 0.90 (the 3-level label alone: 0.96) | **44 of 55** | **11** | **0** |

Combined with the model's own refusals (the real system), both ship no wrong answer here, and the check answers 44 questions
where the reranker gate answers 31. The judge flagged none of the 44.

What it shows, and what it doesn't:

1. **It is more useful than the reranker score,** removing 13 needless refusals while still blocking u03 and b03 (the model
   called both `partial`). Without those two (the failures I had already seen when I wrote it) the numbers are the same: 44 of
   55 answered, 23 of 23 unanswerable refused. I wrote the prompt once, before any run, and did not change it afterwards.
2. **It is stable, unlike the judge.** I ran it twice from scratch: the label was identical on **79 of 80** questions, the
   answer-or-refuse decision on **80 of 80**, and the totals and AUROC were the same. (The judge's verdict on u03 varied
   between runs.)
3. **The quote check never fired.** In both runs all 44 `full` answers had a quote that was really in the passages (0
   fabricated). So the gain comes from the model's own label, and the verification is a safeguard I have not seen working.
4. **It is conservative.** It refused 11 answerable questions (4 direct, 7 paraphrased). Two of them (q17, q33) were right
   to refuse, since the passages lacked the answer. The other **9 were needless**: it says `partial` when a passage states
   the fact in words that differ from the question ("Who handles card dispute processing?", "What is PSD3?"). The
   reranker gate had 22 needless refusals, so this is 9 against 22, not zero.
5. **It is yes or no.** The reranker score gives a ranking and the check does not (ties go to the reranker score if you
   need an order). It also adds one more model call per question (roughly 1,000 input tokens, an estimate); I did not
   time it.
6. **Quote present is not the same as answer correct.** The check shows a real sentence exists; it does not show that the
   sentence answers the question, and the same model wrote the label.

**Caveats:** 25 unanswerable questions, all mine (18 written for the reranker abstain work, before this check; 2 failures
seen before it);
one corpus; `gpt-4.1-mini` as both generator and checker (a different model is untested); the checker has not been tried
on questions written by someone else.

### Questions from the web that I did not write (`capstone/evals/questions_independent.json`)

Every earlier score used questions written by the same author as the documents. To get wording I did not control, I took 44
real questions: 27 question titles from Quora (found by topic searches, in the order the search returned them) and the 17
questions on the PCI Security Standards Council's FAQ page (as returned by an automated fetch, in page order). Each question
records its source. I excluded multi-part questions where only the first part is covered, truncated titles, blog headings and
results that were not about payments (ISO 22000 food safety, crypto "ISO" coins). The PSD2 and PCI searches on Q&A sites
returned no usable questions, and NPCI's FAQ pages would not load, so those topics are thin.

**Only 9 of 44 (20%) can be answered from the corpus.** That is a finding in itself: real people's questions on these topics are
mostly outside an 11-document corpus. The rule for "answerable" was fixed before I looked: a corpus sentence must state the main
fact asked. All 17 PCI FAQ questions (SAQ A, TLS versions, truncated PANs) are expert-level and unanswerable here.

**What "independent" does and doesn't mean.** The question wording is not mine. The topics I searched, the exclusion rule, the
answerable/unanswerable labels and the gold phrases are mine, and only 9 questions are answerable, so one question is worth 0.11.

**Retrieval on these questions:**

| Hit@k (structure-aware chunks) | My dev questions | These independent questions |
|---|---|---|
| Local TF-IDF, Hit@3 | 0.72 | **0.89** |
| Local BM25 + stemming, Hit@3 | 0.81 | **0.44** |
| Azure hybrid, Hit@1 | 0.70 | **0.33** |
| Azure hybrid, Hit@3 | 0.88 | 0.67 |
| Azure hybrid, Hit@5 | 0.93 | **1.00** |

- **The BM25 and stemming gain did not generalise.** On my questions it looked best (0.81 vs 0.72); on these it is clearly worst
  (0.44 vs 0.89, four questions of nine). I had warned the gain came from fixing failures I had already seen, and this is
  consistent with that, but nine questions is small and I did not investigate why stemming hurts here.
- **Azure hybrid search puts the right chunk first far less often on unfamiliar wording** (Hit@1 0.33 to 0.44 against 0.40
  to 0.70), yet the answer is in the top 5 for every question except one (semantic chunks, 0.89). The three structure-aware misses
  at Hit@3 are all at rank 4. Since the pipeline reranks 10 candidates, rank 4 to 5 is recoverable.
- **The strategy ranking changed** (recursive 0.78 is best at Hit@3 here, structure-aware 0.67), which is one question; I would
  not read anything into it.

**Abstaining on these questions** (nothing tuned: the 4.41 threshold and the prompt were fixed before these questions existed):

| | Reranker gate | Quote-verified check |
|---|---|---|
| AUROC (all 44) | 0.83 | 0.80 as yes/no, **0.92** as the 3-level label |
| Answerable answered | 5 of 9 | 6 of 9 |
| Unanswerable refused | 34 of 35 | 33 of 35 |
| Wrong answers shipped | 1 (iu08) | 2 (iu05, iu08) |
| Made-up quotes | n/a | 0 |

- **The check's advantage on my own questions did not clearly replicate.** There it answered 44 of 55 against 31, at the same
  safety. Here it answers 6 against 5 and ships one more. With 9 answerable questions that is within noise: I can't say the
  check is better or worse.
- **The two gates make different mistakes.** The check answered the broad "how does it work" and "what are the steps" questions
  (i02, i04) that the reranker scored low (-6.39 and -0.33), and it answered the "full name of UPI" question the reranker scored
  3.97, just under the threshold. The reranker answered i05 (UPI security), whose passages did not contain the answer.
- **All 17 PCI FAQ questions were refused by both gates.** Expert-level questions on a topic the corpus only touches are reliably
  turned away, which is the abstain behaviour working.
- **The "mistakes" are partly my labelling.** iu05 ("Do someone uses UPI for regular payments? What are their reviews?") breaks
  my own exclusion rule: its first part is covered by the sentence the check quoted, so it should have been excluded. iu08
  ("Can I dispute a credit card charge after 60 days?") is debatable, since the corpus states the 60-day rule and an answer quoting
  it is responsive, not made up. Excluding iu05 and reclassifying iu08 would leave the check shipping 0 or 1. I did not change
  the labels after seeing the results, so they are reported as they stood.
- **Two answerable questions were lost to retrieval, not to the gate** (i05 and i07, the UPI security questions): the
  authentication passage was not among the top 3 (the top result for i07 was the PCI DSS summary).

### Round 2: the ingestion pipeline and the corpus checks (`payments_rag/ingestion.py`)

**The pipeline.** Before this, documents were read by whichever script needed them, the registry was trusted, and nothing
noticed when a document changed. Now `python -m payments_rag.ingestion` does three things:

1. **Validates the registry** (`sources.json`) against the files and reports every problem at once: duplicate ids or files, a
   missing file, an unknown verification level, a date that is not YYYY-MM-DD, a web-fetched document with no retrieval
   date, a repealed document that names no replacement, a source that is neither author-written nor given a public https
   URL, and any file in `raw/` that is not registered. Planned documents without a file are skipped.
2. **Cleans each document** (`clean_text`): removes a byte-order mark, normalises line endings, strips trailing spaces, drops
   the meta sections, collapses blank lines. It does not rewrite words, and cleaning twice gives the same result.
3. **Writes `processed/manifest.json`** with a hash of every raw and cleaned document. `--check` fails when a document has
   changed since, a test does the same in CI, and an Azure index record (`evals/azure_index_manifest.json`, written when the
   index is built) lets `--check-index` say whether the live index matches the corpus. That is the check I lacked when the
   index silently kept the repealed RBI text.

12 tests cover it, including one that proves ingestion produces **exactly the same chunks** as the earlier
raw-text-plus-strip path for all four strategies, so earlier evaluation results remain valid, and one that checks every gold
phrase of every question file survives cleaning. The evaluation scripts now load documents through the validated registry.
What it cannot do: decide that a document is public or non-confidential. That remains a human responsibility.

**Verifying the unverified documents.** I tried every route that was open. What I found:

| Document | What I checked it against | Result |
|---|---|---|
| Card-scheme summary | ECB Glossary of payment, clearing and settlement terms (30 Sep 2008; the PDF text read directly) | Issuer, card scheme, clearing and settlement are defined consistently. The glossary's acquirer is the entity to which the acceptor (usually a merchant) transmits the information needed to process the card payment, which is looser than "the bank that handles the merchant's account". The authorization step is still supported only by search summaries of Mastercard (403). |
| ISO 20022 overview | BIS report "Harmonisation of ISO 20022" (9 Sep 2022), fetched | Supports "a messaging standard most payment systems are adopting" and use by payment system operators. Not confirmed: corporations and regulators as users, the concept list, the example message. The ISO site returns 403. |
| RBI payment-systems summary | RBI Master Direction on Digital Payment Security Controls (18 Feb 2021) and the 2025 Directions, fetched | Secure payments, authentication and fraud controls, risk and governance, and customer protection are supported. **"System resilience and operational continuity" is not: the 2021 Master Direction's fetched summary reports no mention of business continuity.** The infrastructure topic was not checked. |
| FAQs | Visa dispute FAQ (April 2020, text extracted from the PDF), CFPB, PCI SSC, the other corpus documents | "Non-receipt" as a dispute reason is supported by Visa's "Merchandise/Services Not Received" condition, "billing problems" by CFPB. "Fraud" is in neither. FAQ 6 is about this RAG system, not payments. |

I did **not** delete or rewrite the unsupported RBI claim, because two questions use that exact phrase as their gold answer.
Instead the bullets are annotated "(not confirmed in the sources checked)" and the document ends with a source note, so a
grounded answer that quotes them carries the warning. The other three documents also got a source note.

New verification level `author_written_partly_verified` means "author-written, some claims checked against fetched sources,
others not", with `checked_against` listing the sources and the notes saying which claims each supports. The registry now
holds: 4 fetched, 1 fetched plus search summary, 2 search summary only, 4 author-written and partly verified.

**Dates.** The CFPB page shows "last reviewed 15 Apr 2024" (modified 3 May 2024), so it now has a date. **Dates are still `null`
for 7 of 11 documents.** For author-written summaries there is no publication date, and for the NPCI and ISO pages no
date was readable. I did not guess.

**After the document changes** the Azure index was stale again, so I rebuilt it; `--check-index` now reports it matches. The
retrieval results moved by at most one or two questions on every split (for example dev structure-aware Hit@3 0.88 to 0.91,
held-out 0.83 to 0.92, independent Hit@3 unchanged at 0.67), so the annotations did no harm. **The grounding, citation and
answerability runs predate these annotations**, and the RBI wording changes could alter answers to the resilience questions
(q14, q22); I have not repeated them.

### What I fixed in the review of this week's code

- The recursive chunker silently dropped text: a 400-word section kept 78 words. Fixed, with a test.
- A heading followed by a blank line became its own chunk, so 25 of 49 recursive chunks and 25 of 107
  structure-aware chunks were headings only. Fixed: headings now travel with their body.
- The "semantic" strategy is a hand-written keyword-topic list, not embeddings. It is now documented as
  that, and `similarity_threshold` really controls merging (it did nothing before).
- `compare_chunking_strategies` gave one `max_chunk_size` to sentences and words alike. Split into two.
- The `Chunk` class was never used, so no chunk carried its document, section or URL. `chunk_document`
  now attaches them.
- Retrieval rebuilt its index on every query and returned zero-score chunks as "results". Now `Retriever`
  indexes once and returns only chunks that share terms with the query.
- The first evaluation had four questions and counted a hit when any keyword appeared in the top chunk
  (nearly the signal TF-IDF ranks on), never checked `expected_doc`, and left out the FAQ file. All four
  strategies scored 100%, so it could not tell them apart. The new evaluation replaces it.
- CI would have failed on 8 lint errors and a formatting check. Fixed. Tests went from 23 to 111 (plus one that needs a model download).
- `sources.json` listed PSD2 and PCI-DSS as "planned", had no publication dates, and no way to tell which documents were checked against a source. Now every entry has a file, a date where known, and a `verification` field, and a test keeps the registry and the files in sync.

### What confused me

*(Draft. Edit it so it is honest to you.)*

- My first chunking result (structure-aware 0.71 vs 0.58) shrank to 0.49 vs 0.44 on a bigger corpus. I had
  half-believed a three-question gap.
- More documents made retrieval harder, not easier: more near-duplicates and more distractors.
- Five questions failed in every chunking strategy. The problem was matching words, not cutting text.
- A similarity score looked like confidence, but unanswerable questions scored higher than answerable ones.
- Two of the official pages (ISO 20022 and NPCI) wouldn't load for automated fetching, so I could only record
  them as "via search summary". Knowing how well a fact is sourced matters.

### One number that moved

Hit@3 for fixed-size chunking: **0.96 on 4 documents, 0.72 on 10 documents**. The first evaluation was too
easy to be informative; the harder one is the first that can tell a retriever's weaknesses.

### One interview question I can now answer

**"What is chunking in a RAG system, and why does it matter?"**

Chunking splits documents into the pieces that get embedded and retrieved. Each chunk has to be
self-contained enough to answer from, so I keep the section heading on it, never cut a list item in the
middle, and carry the source and section as metadata so an answer can cite it. I compared four strategies on
43 questions with an exact gold-phrase check. No strategy clearly won: structure-aware led on direct questions,
fixed-size on paraphrased ones, and the keyword-topic "semantic" chunker was clearly worst. Five questions
failed in every strategy because of vocabulary mismatch, so chunking only goes so far and retrieval has to
improve too. The lessons I keep: indexing meta text can make a chunk beat the real answer, a small evaluation
can show a gap that disappears at scale, and a retrieval score can't tell me when to abstain.

### Still to do

- [x] Verified the unverified documents as far as the sources allow, and annotated what could not be confirmed (see Round 2).
      Still blocked: the ISO, Mastercard and NPCI pages (403 or no text) and the RBI Payments Vision page (CAPTCHA).
- [ ] Grow the corpus further (dozens of documents, longer ones), so chunk boundaries finally matter. Publication dates
      are `null` for 7 of 11 documents because the sources show none.
- [x] Cheap retrieval fixes: stemming and BM25 tried (dev gains, not confirmed on held-out questions).
- [ ] Test the "longer chunks help paraphrases" hypothesis with different chunk sizes.
- [x] An independent question set from the web (44 questions, 9 answerable) is in place and scored. Still open: a set
      written by a person who has not read the corpus, with labels and gold phrases that are not mine (the format and
      checks are in `capstone/evals/README.md`). The web set has too few answerable questions (9) to separate close methods.
- [x] Embeddings and hybrid search tried locally (all-MiniLM-L6-v2): the first clear gain.
- [x] Azure infrastructure as Bicep, deployed to the free account, keyless; smoke test passes on live Azure.
- [x] Ran `evaluate_azure.py` and compared with the local hybrid result (see above).
- [x] Azure's semantic ranker tried and measured (see reranker section). Still open: a cross-region latency fix (OpenAI and Search in one region), then re-measure.
- [x] Ran the grounding rule end to end on Azure on the 80 questions and measured groundedness.
- [ ] Tear down (`infra/teardown.ps1`) when finished, or leave running (OpenAI bills per token only; free Search
      may be deleted if idle).
- [x] Reranker added and measured as an abstain signal (AUROC 0.79).
- [ ] Add a true semantic chunker using sentence embeddings.
- [x] Grounding rule for retrieval: rerank, threshold, abstain, cited prompt (`grounding.py`).
- [x] Connected `gpt-4.1-mini` on Azure OpenAI to the grounding rule (see above).
- [x] Citations: the strict prompt raised coverage from 78% to 98%; enforcement and a retry reach 100% (retry rule tightened
      after a live test). Still open: citations whose passage does not support the sentence.
- [ ] Get a better verifier than the same-model judge: use a different model (e.g. `gpt-5-mini`, which this account has
      quota for) and hand-label a sample of answers to measure how often the judge is right (it missed b03).
- [x] Reduced the cost of the gate: the quote-verified answerability check answers 44 instead of 31 with nothing wrong
      shipped. Still open: a different checker model, independent questions, and a cost that makes a wrong answer worse
      than a refusal.
- [ ] Fix the retrieval misses that cause the real failures (q17, q33), since generation is not the weak link.
- [x] Committed and pushed (`be2072b`, then `d6ee1e6` to fix CI).

## Reranker section: hybrid vs local cross-encoder vs Azure semantic ranker

Run with `uv run --all-groups python capstone/evals/evaluate_rerankers.py` (needs `az login`). Same structure-aware index, same questions, three orderings.

| Set (answerable n) | hybrid Hit@1 / MRR | + local cross-encoder | + Azure semantic ranker |
|---|---|---|---|
| dev (43) | 0.70 / 0.81 | 0.70 / 0.82 | 0.86 / 0.92 |
| heldout (12) | 0.67 / 0.78 | 0.67 / 0.82 | 0.92 / 0.96 |
| corpus_update (5) | 0.40 / 0.49 | 0.60 / 0.70 | 0.80 / 0.87 |
| independent (9) | 0.33 / 0.58 | 0.67 / 0.80 | 0.78 / 0.87 |

- The semantic ranker is best on every set, on Hit@1 and MRR. Hit@3 reaches 0.98-1.00 on all four sets.
- The local cross-encoder adds little on dev and heldout, but helps clearly on the two newer sets.
- Honest limits: the 9- and 5-question sets move 11 and 20 points per question; the questions are mine; one run; the free tier's
  semantic allowance (about 180 queries a month) is now mostly used. Query time was similar (0.4-0.6 s).
- Not yet tried: feeding the semantic reranker score to the abstention gate (it is on a 0-4 scale, unlike the local score).


## The `ask` command (retrieve -> generate in one step)

```
uv run --project capstone --all-groups python -m payments_rag.ask "What is ISO 20022?"
```

Run from the repo root (that is where `.env` is). Hybrid search with the semantic ranker returns the top 3 passages; the quote-verified
answerability check decides whether they fully answer the question; then a cited answer is written, or the assistant refuses and says why.
Sources lists only the passages the answer cites.

Live spot checks (not a measurement): "What is ISO 20022?" and "What is remittance information?" were answered with citations; the 2011
cricket question was refused ("none"); the pacs.008 and Visa card-not-present chargeback questions were refused as "partial". I have not
checked whether those two refusals are right or too strict. The measured refusal behaviour is in the abstention and answerability sections above.

## Licence field and metadata filters (closing the small Week 4 gaps)

**Licence.** Every registry entry in `sources.json` now has a required `licence` (an empty value is a registry error). Honest state: the
4 author-written documents say `author_written`; the other 7 say `not_checked`. I did not look up the licences or terms of use of the public
sources, so those 7 are still a to-do before anything is republished.

**Filters.** Chunks now carry `jurisdiction` (region), `source_type` and `published`, and the Azure index has them as filterable fields.
`SearchFilter` (in `search_filters.py`, no Azure imports) turns source, region, type and date range into an OData filter, applied before ranking.
`python -m payments_rag.ask "..." --source psd2_overview --region EU --published-from 2025-01-01` uses them (names are matched ignoring case; an
unknown value is an error that lists the valid ones). Values are validated, so a filter value cannot break out of the OData string.

Checked live after rebuilding the index (52/63/100/63 chunks, index matches the corpus): for "rules for authenticating card payments", no filter
returned the repealed 2016 RBI circular first; `--region India` returned only India documents; `--source psd2_overview` only PSD2;
`--published-from 2025-01-01` returned the 2025 RBI directions and PSD2 and dropped the 2016 circular.

Limits: matching is exact (`India` does not include `global` documents); a date filter drops the 7 documents with no published date; filters
exist for Azure search only, not the local retriever; filtered retrieval is not part of the evaluation tables.
