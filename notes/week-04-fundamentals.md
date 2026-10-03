# Week 4 fundamentals, explained with your exercise

Every number below comes from `capstone/evals/evaluate_chunking.py` on the public payments corpus (10 documents, about 2,400 words: ISO 20022, card schemes, RBI guidance, PCI DSS, PSD2, CFPB, UPI and FAQs) and 48 questions (43 answerable, 5 not). The code is in `capstone/src/payments_rag/`. Retrieval here is **TF-IDF**, not embeddings; embeddings and Azure AI Search come next.

Contents: 1. What RAG is · 2. The pipeline · 3. Chunking · 4. Metadata and citations · 5. Retrieval with TF-IDF, BM25 and stemming · 6. Evaluating retrieval · 7. Your results · 8. Corpus lessons · 9. Grounding and abstaining · 10. Where Azure fits · 11. Interview check

---

## 1. What RAG is, and why

A language model answers from what it learned in training. That has three problems for a payments assistant: it can be **wrong and sound sure** (hallucination), it **can't know your documents** (a bank's own rules, recent regulation), and it **can't show where an answer came from**.

**Retrieval-augmented generation (RAG)** fixes this by splitting the job:

```
question → RETRIEVE the relevant passages from your documents → GENERATE an answer using only those passages → CITE them
```

The model is no longer asked to remember facts. It is asked to **read the evidence it is handed and answer from it**. This week builds the first half: the evidence layer. The quality of the final answer is capped by it: if the right passage isn't retrieved, no prompt can recover it.

---

## 2. The pipeline

| Stage | What happens | In your code |
|---|---|---|
| **Ingest** | load public documents, keep their source info, drop what shouldn't be indexed | `load_documents`, `strip_sections`, `sources.json` |
| **Chunk** | cut each document into retrievable pieces | `chunk_text`, `chunk_text_recursive`, `chunk_text_semantic`, `chunk_text_structure_aware` |
| **Attach metadata** | record document, section, URL, strategy on each chunk | `chunk_document` → `Chunk` |
| **Index** | turn every chunk into a searchable vector | `Retriever.__init__` (TF-IDF) |
| **Retrieve** | find the top-k chunks for a question | `Retriever.search` |
| **Generate + cite** | answer from the chunks and point to them | *not built yet* |
| **Evaluate** | measure each stage separately | `evaluate_chunking.py` |

**Evaluate each stage on its own.** A wrong final answer could come from bad chunking, bad retrieval or bad generation. Measuring retrieval separately (this week) tells you which one to fix.

---

## 3. Chunking

**Why chunk at all.** A whole document is too long and mixes topics, so one vector can't represent it well and a model's context window is limited. A single sentence is too small to answer from. A chunk should be **one coherent idea with enough context to stand alone**.

- Too big: the retrieved chunk is mostly noise and a match on one idea drags in others.
- Too small: the answer is split across chunks and each piece loses the context that makes it meaningful ("it is settled the next day" means nothing without knowing what "it" is).

### The four strategies

| Strategy | How it cuts | Strength | Weakness |
|---|---|---|---|
| **Fixed** | a sliding window of N words with overlap | simple, fast, predictable size; the baseline | ignores structure, so it can cut a sentence or a list in half; headings and line breaks are flattened |
| **Recursive** | by headings first, then paragraphs, then word windows; keeps the nearest heading on each chunk | respects natural boundaries; sizes stay close to the target | only knows headings and paragraphs, not lists or tables |
| **Semantic** | groups neighbouring sentences that share a topic | keeps related ideas together; chunk sizes follow meaning | yours is a **keyword-topic heuristic**, not embeddings, so it only knows the topics in its list |
| **Structure-aware** | like recursive, but keeps the **whole heading path** (`# Doc` then `## Section`), never splits a list item, keeps tables whole | each chunk says where it lives; lists stay intact | needs well-structured source documents |

Key parameters: **chunk size** (about 80 words here) and **overlap** (20 words for fixed windows: repeated words at the edges so an idea cut at a boundary still appears whole in one chunk). Overlap costs index size and creates near-duplicates.

**Headings travel with the chunk.** Putting `## Core concepts` on every chunk from that section means the chunk still announces its topic when it is retrieved alone, and the heading words help it match questions.

### What the semantic chunker really does

Each sentence is tagged with topics from a word list (authorization, settlement, dispute, payment, messaging, security). A sentence joins the current group when the **Jaccard overlap** of their topic sets (shared topics divided by all topics) reaches `similarity_threshold`; a threshold of 0 merges everything up to the sentence limit. It is honest and cheap, but a sentence about "chargebacks" and one about "disputes" only group if both words are in your list. A real semantic chunker compares **sentence embeddings** instead, so it can group by meaning without a word list. That is future work.

### A bug worth remembering: silent data loss

The first recursive chunker cut long sections with `rest[: chunk_size * 6]`: a 400-word section kept **78 words** and said nothing. The lesson: **a chunker must lose nothing**, and the way to catch it is a test of an invariant ("joining all the chunks gives back every word"), not just examples of what the output looks like. The new test does exactly that.

---

## 4. Metadata and citations

A chunk is not just text. Each one carries:

| Field | Example | Used for |
|---|---|---|
| `doc_id` | `card_scheme_public_summary` | which document it came from |
| `section` | `Card scheme public summary > Core concepts` | which part, for the citation |
| `source_url` | `https://www.visa.co.in/...` | linking the user to the source |
| `strategy`, `chunk_index` | `structure_aware`, 2 | comparing strategies, debugging |
| `title` | `Card scheme rules and payment lifecycle overview` | display |

Without this, an answer can't say where it came from. Keeping metadata with every chunk is what makes **"cite the evidence"** possible later, and it is also what lets the evaluation check *which document* a result came from. Fixed chunking cannot supply a section, because it flattens structure: another cost of that baseline.

`sources.json` also records jurisdiction, source type and status. It is missing **publication dates**, which matter for regulation (a rule can be superseded).

---

## 5. Retrieval with TF-IDF

**TF-IDF** scores words by how useful they are for telling documents apart:

- **TF (term frequency):** how often a word appears in this chunk. More is a stronger signal.
- **IDF (inverse document frequency):** how rare the word is across all chunks. A word in every chunk ("payment") says little; a rare word ("chargeback") says a lot.
- Each chunk becomes a vector of TF x IDF weights, and a question becomes a vector the same way. **Cosine similarity** between the two vectors (1 = same direction, 0 = no shared terms) ranks the chunks.
- `stop_words="english"` drops words like "the" and "is".

**Strengths:** no model to download, fast (about 1 ms per query and under 2 ms to index the whole corpus), easy to explain.

**The big limit: it is lexical.** It matches **words**, not meaning. "Which bank looks after the shop's account?" shares almost no words with "Acquirer: the bank that handles the merchant's account." A paraphrase can fail even when the meaning is identical. **Embeddings** fix this by mapping text to vectors where similar meanings sit close together, so a question and its answer match even with different words. They are the next step, and the same evaluation will measure the gain.

### BM25: a better scoring formula for the same words

BM25 is the standard keyword-search formula (it powers most traditional search engines). For each query word it
adds:

```
idf(word)  x  tf x (k1 + 1) / ( tf + k1 x (1 - b + b x chunk_length / average_length) )
```

- **Saturation (`k1`, default 1.5):** repeating a word helps, but with diminishing returns. A chunk saying "fraud"
  ten times is not ten times as relevant as one saying it once (a test checks this).
- **Length normalisation (`b`, default 0.75):** a long chunk gets less credit than a short one for the same word
  count, because long chunks contain more words by chance.
- Unlike TF-IDF's cosine similarity, scores are not between 0 and 1 (here about 7 to 10), and they only make sense
  within one index.
- A hand-calculated example is in the tests: with 2 chunks and a word in 1 of them, the score is exactly ln 2.

### Stemming: matching different forms of a word

A **stemmer** chops words to a root so different forms match: "applies" and "apply" both become "appli"; "relaxed"
and "relaxation" become "relax". Your question "Who does PCI DSS apply to?" could not find "Who it applies to"
without it. Limits: it unifies spelling variants only partly (UK "authorisation" stems to "authoris", US
"authorization" to "author"), it can merge unrelated words, and it cannot link words that mean the same but look
different ("charge extra for paying by card" vs "retailer surcharges"). That last problem needs embeddings.

### What the experiment showed

Hit@3 with structure-aware chunks (dev set of 43 questions / held-out set of 12):

| Retrieval | Dev | Held-out |
|---|---|---|
| TF-IDF | 0.72 | 0.83 |
| TF-IDF + stemming | 0.79 | 0.75 |
| BM25 | 0.74 | 0.83 |
| BM25 + stemming | **0.81** | 0.83 |

- **Dev gains are optimistic.** I picked stemming after looking at which dev questions failed, so improving on them is
  partly circular. That is why 12 questions were written *before* the code change and scored once.
- **They did not clearly carry over.** Held-out scores were flat or slightly lower (one question = 0.083). The honest
  conclusion is "plausible, unproven".
- **Stemming made abstaining harder:** unanswerable questions scored relatively higher once more words matched
  (ratio of top scores 1.14, then 1.23 with stemming and 1.31 with BM25 + stemming).
- **Lesson:** use a held-out set whenever you choose a fix by looking at failures, and make it big enough to detect
  the change you care about.

### Embeddings: matching meaning, not words

An **embedding model** turns a piece of text into a list of numbers (384 for all-MiniLM-L6-v2) so that texts with
similar meaning get vectors that point in similar directions. Retrieval becomes: embed every chunk once, embed the
question, and rank chunks by **cosine similarity**. A quick check I ran: "Can shops charge extra
for paying by card?" scores 0.61 against "It bans retailer surcharges for card use" and 0.17 against an unrelated
sentence about settlement, although the two related sentences share almost no words.

- **Strength:** paraphrases, synonyms, different wording. It found the one question lexical search never could.
- **Weaknesses:** rare exact tokens and codes ("pacs") can be blurred; it costs a model and more time (about 8 ms a
  query on a CPU vs 0.4 ms for BM25); and the model only reads a limited length (about 256 word pieces for MiniLM),
  so long chunks are silently cut off.
- **Azure note:** the same idea is what Azure OpenAI embeddings and Azure AI Search's vector search provide. The code
  takes any "texts in, vectors out" function, so swapping the model changes one line.

### Hybrid search and reciprocal rank fusion (RRF)

Run the keyword and the embedding search, then merge the two ranked lists. **RRF** scores each chunk
`sum over lists of 1 / (60 + rank)`. A chunk ranked high by both rises to the top; one found by only one list still
appears. It uses ranks, not raw scores, so BM25 scores (about 8) and cosine scores (below 1) need no common scale.
The constant 60 is the usual default and was not tuned.

Why it works here: the two methods make **different mistakes**. Embeddings caught "charge extra" ~ "surcharges";
BM25 + stemming caught the exact token "pacs" and "apply" ~ "applies". Together they recovered all 5 questions every
earlier method missed.

Results, structure-aware chunks, Hit@3 on the dev set (43) and held-out set (12):

| Retrieval | Dev | Held-out |
|---|---|---|
| TF-IDF | 0.72 | 0.83 |
| BM25 + stemming | 0.81 | 0.83 |
| Embeddings | 0.88 | 0.92 |
| Hybrid | **0.95** | 0.92 (Hit@5 1.00) |

- Ten more dev questions answered than with TF-IDF is far above noise (one question = 0.023); the held-out set agrees in
  direction but is too small (one question = 0.083) to confirm the size.
- **Chunking mattered again** once retrieval was semantic: structure-aware 0.88 vs fixed 0.72, recursive 0.70, semantic 0.63.
  A guess: the heading path gives each vector topic context. Not tested.
- **Hit@1 did not improve on held-out** (0.58 vs 0.67): hybrid is better at "somewhere in the top few" than at "first".
- **Abstaining is still unsolved.** AUROC of the top score for answerable vs unanswerable questions: 0.48 (TF-IDF),
  0.45 (BM25 + stemming), 0.57 (embeddings), 0.53 (hybrid). That is about chance (only 7 unanswerable questions, so
  the uncertainty is wide). A **reranker** (a model reading question and chunk together) or a model check of the
  evidence is the next thing to try.

### Reranking: a second, slower, more careful look

Retrieval finds candidates fast by comparing stored vectors or words. A **cross-encoder reranker** then reads the
question and each candidate **together** as one input and outputs a relevance score. It can notice things a stored
vector can't (negation, what the question is really asking), but it must run once per candidate, so you use it only
on a short list (10 chunks here). This two-step shape, *retrieve many cheaply, rerank a few carefully*, is standard in
production search.

Result: the right chunk came first more often (dev Hit@1 0.60 to 0.74; held-out 0.58 to 0.67). Its raw scores are
logits on an arbitrary scale (about -11 for unrelated text, about -4 for a good match), so "relevant enough" has to be
learned from data.

### The grounding rule and abstaining

A grounded assistant answers **only from retrieved evidence**, cites it, and says it doesn't know when the evidence
isn't there. The rule built here:

```
retrieve 10 candidates (hybrid) -> rerank them -> best score >= threshold?
    yes: pass the top 3 passages to the model, told to answer ONLY from them and cite [1], [2], ...
    no:  abstain; pass NO evidence, so the model cannot answer from memory by accident
```

Which score decides? AUROC (how well a score separates answerable from unanswerable questions; 1.0 perfect, 0.5 chance):

| Signal | AUROC (all questions) |
|---|---|
| BM25 | 0.58 |
| Embedding similarity | 0.68 |
| Hybrid score | 0.56 |
| **Cross-encoder reranker** | **0.79** |

- **Retrieval scores measure "how close is the nearest passage", not "does it answer the question".** An unanswerable
  question about PCI DSS is close to the PCI DSS document. A reranker, which reads question and passage together, judges
  answering more directly, so it separates better. It is still imperfect.
- **The threshold is a cost trade-off.** Refuse 100% of unanswerable questions and you answer only 42% of answerable
  ones; refuse 90% and you answer 60%. A wrong answer in payments is usually worse than a refusal, so lean strict, and
  soften the refusal (show the sources, or ask the user to rephrase).
- **Thresholds don't transfer between kinds of question.** Chosen on mostly direct questions, it refused 7 of 12
  paraphrased held-out questions that were answerable. Calibrate on questions that look like real users' questions.
- **Choose the threshold on one set and judge it on another**, or the result is optimistic (Week 1's lesson again).
- **What's measured and what isn't:** this is the retrieval half of grounding. *Groundedness* of a generated answer
  (every claim supported by a cited passage) needs a language model and is still to do.

### Measuring groundedness (what "answers from the evidence" means in numbers)

Once a model writes answers, retrieval metrics aren't enough. Four things to measure, kept separate:

| Question | How it was measured here | Result |
|---|---|---|
| Does it **refuse** when the passages don't answer? | unanswerable questions; count replies that are not "I don't know" | the model alone refused 23 of 25 |
| Is the answer **correct**? | a judge compares it with the reference fact | 52 of 53 answered, correct |
| Is every claim **supported** by the passages? | a judge checks each claim against the passages shown | 95% (judge's view; see below) |
| Are **citations** present and valid? | code: has a [n], and n is a real passage; share of sentences with one | 100% / 78% |

- **Split failures into retrieval vs generation.** For each answerable question, record whether the retrieved passages
  contain the answer. When they did, the answers were right 52 of 52; the failures came when they didn't. This tells you
  where to spend effort (here: retrieval, not the prompt).
- **A judge model is a tool, not the truth.** An LLM that checks answers can be wrong and, when it is the same model that
  wrote them, tends to agree with itself. Here the judge missed a real error (it called a mix-up of a transaction limit and a
  liability amount "supported", because every word came from the passage) and flagged a false positive. Read the flagged
  and borderline cases yourself, use a different model as judge where possible, and hand-label a sample to measure the
  judge's accuracy.
- **"Supported" is not "answers the question".** An answer built only from words in the passages can still answer a
  different question. Check support *and* correctness.
- **Right but ungrounded is still a failure.** "pain" really is the message family for customer credit transfers, but the
  sources didn't say so, so a grounded assistant should not state it as fact.
- **Citation coverage needs enforcing.** Telling the model to cite every claim gave 78% of sentences cited. If citations
  matter, check them in code (drop or flag uncited sentences) rather than trusting the instruction.
- **A threshold guard is a cost trade-off.** The reranker gate removed the last two bad answers but refused 22 answerable
  questions the model had answered correctly. Report both numbers, and choose using the relative cost of a wrong answer
  and a refusal.
- **Operational detail:** Azure OpenAI limits both tokens and requests per minute. Short replies (refusals) hit the request
  limit first. Pace calls, retry on 429, and save progress so a failure doesn't throw away finished work.

**Practical changes made to the retriever:**
- Build the index **once** and reuse it for many queries (the first version rebuilt it for every question).
- Return only chunks with a **score above 0**. A chunk sharing no words with the question isn't evidence, and an empty result should mean "I found nothing", which a grounded answer must respect.

---

## 6. Evaluating retrieval

**The first evaluation was weak** (and its flaws are the lesson):
- 4 questions, so one question moved the score by 25 points.
- A "hit" meant any keyword appeared in the top chunk. That is nearly the same signal TF-IDF ranks on, so the test was **circular**: the metric agreed with the retriever by construction.
- `expected_doc` was recorded but never checked.
- The FAQ file wasn't indexed.
- All four strategies scored 100%, so it **could not tell them apart**. An evaluation that cannot fail is not measuring anything.

**The new design:**

| Idea | How |
|---|---|
| **Gold phrase** | each question lists the exact sentence fragment, and the document it lives in, that answers it. A test confirms every phrase really is in its document. |
| **A hit** | one of the top-k chunks is from the expected document **and** contains the gold phrase |
| **Alternatives** | many questions have several valid sources (the ISO answer is in the overview and in the FAQ); any counts |
| **Question kinds** | 28 direct (words match the source), 15 **paraphrased** (words differ), 5 **unanswerable** (the corpus has no answer) |

**Metrics:**

| Metric | Meaning |
|---|---|
| **Hit@k** | share of questions whose correct chunk is in the top k. Hit@1 = the very first result is right. |
| **MRR@10** (mean reciprocal rank) | average of 1 / (rank of the first correct chunk). Rank 1 gives 1, rank 2 gives 0.5, rank 4 gives 0.25. Rewards putting the answer high. |
| **Gold phrase intact** | whether any chunk still contains the whole gold phrase, i.e. the chunker didn't cut the answer in two |
| **Top score on unanswerable questions** | whether the similarity score can be used to decide "no answer" |

**How much to trust a number.** With 43 questions, **one question is worth 0.023** (with the first 24 it was 0.042). A gap of 0.02 to 0.05 is one or two questions, which is noise (the Week 2 lesson again). Only large, consistent gaps count.

---

## 7. Your results

Meta sections removed at ingestion, 10 documents, 43 answerable questions:

| Strategy | Chunks | Hit@1 | Hit@3 | Hit@5 | MRR@10 | Hit@3 direct | Hit@3 paraphrased |
|---|---|---|---|---|---|---|---|
| fixed | 39 | 0.44 | **0.72** | **0.88** | **0.62** | 0.71 | **0.73** |
| recursive | 48 | 0.42 | 0.65 | 0.79 | 0.57 | 0.71 | 0.53 |
| semantic (keyword topics) | 78 | 0.30 | 0.58 | 0.70 | 0.47 | 0.61 | 0.53 |
| structure_aware | 48 | **0.49** | **0.72** | 0.86 | **0.63** | **0.82** | 0.53 |

Reading it:
- **No strategy clearly wins.** Fixed and structure-aware tie at Hit@3. Structure-aware leads at Hit@1 and on direct questions; fixed leads on paraphrased ones. Each gets right some questions the other misses.
- **An earlier hint disappeared.** On the first 4-document corpus structure-aware had Hit@1 0.71 against 0.58 for fixed (three questions out of 24). On 10 documents it is 0.49 against 0.44. A small gap on a small test is a hint, not a result.
- **Semantic is clearly worst** (Hit@1 0.30, 78 chunks, some of only 6 words). A keyword-topic list can only group what it knows. This gap is large enough to trust.
- **The bigger corpus was much harder.** Hit@3 fell from about 0.96 to 0.72, because more documents mean more near-duplicates and distractors. A test that cannot fail teaches nothing; this one can.
- **Five questions fail in every strategy**, so the cause is not chunking. They are vocabulary mismatches ("charge extra for paying by card" vs "retailer surcharges"), a missing stem ("apply" vs "applies"), and TF-IDF's length normalisation (a short chunk full of "ISO 20022" outscored the long chunk containing "pacs"). Fix them with stemming, BM25, embeddings or hybrid search.
- **Longer chunks did better on paraphrases** (0.73 vs 0.53), a hypothesis for more word overlap, not yet tested.
- **The gold phrase was never cut** (intact 1.00 everywhere), so the classic damage from fixed-size cutting still isn't demonstrated on these short, paragraph-based documents.

---

## 8. Corpus lessons

1. **A chunk that lists the question can beat the chunk that answers it.** Your documents have "Practical RAG relevance" and "Example questions this helps answer" sections, which are notes for the learner written as lists of questions. "Who handles card dispute processing?" appears there word for word, so that chunk ranked first and pushed the real answer to rank 4. **Don't index meta text.** `strip_sections` removes them at ingestion, and every strategy improved.
2. **Duplicate content competes with itself.** Authorization vs settlement is explained in both the card summary and FAQ 1. That is why questions accept several valid sources. In production, near-duplicates also waste the top-k slots.
3. **The corpus is the ceiling.** It is now 10 documents and about 2,400 words. Six come from official public pages (PCI DSS, PSD2, the RBI card-not-present circular, CFPB, and two more known only through search summaries), but four older ones are author-written and unchecked. A retrieval system is only as good as its source material.
4. **Record how well each source is verified.** `sources.json` has a `verification` field: `fetched` (read from the official page), `via_search_summary` (the page blocked automated fetching), or `author_written_unverified`. Dates matter too: the RBI circular is from 2016 and later directions exist, so that document carries a caveat instead of presenting old limits as current.
5. **Questions written with the documents are biased.** The direct questions echo the summaries' wording, so the paraphrased ones are the fairer test. Ground truth should ideally come from someone who hasn't seen the answer text.

---

## 9. Grounding and abstaining

A **grounded** answer uses only the retrieved evidence, cites it, and **says it doesn't know when the evidence isn't there**. The three unanswerable questions test the last part: "What are the PSD2 SCA exemption thresholds in euros?", "What is the Visa credit card interchange fee in India?", "Which ISO 20022 message type is used for a credit transfer?".

**The finding:** TF-IDF similarity **cannot** decide when to abstain. The top score for the unanswerable questions was **0.35 to 0.42**, as high as for answerable ones (**0.33 to 0.39**). The reason: both kinds of question share common words ("ISO 20022", "card", "payment") with the corpus. So a rule like "refuse if the best score is below 0.3" would not work.

Better signals, to try later:
- **Embedding similarity**, which cares about meaning not shared words (still imperfect).
- A **reranker** that reads question and chunk together and scores relevance.
- A **model check**: ask the model whether the retrieved text actually answers the question before it writes an answer.
- A rule that the answer must **quote or point to a chunk**, and is rejected if it can't.

A model can sound confident even on weak or irrelevant evidence, so abstaining has to be designed in and tested, not assumed.

---

## 10. Where Azure fits (a preview, not built yet)

This part is general knowledge about the services this roadmap uses, not something implemented here:

- **Azure OpenAI** supplies the **embedding model** (text to vector) and the **chat model** that writes the answer.
- **Azure AI Search** stores the chunks with their metadata and supports keyword search, vector search and **hybrid** (both together), plus an optional semantic reranker.
- Hybrid search is attractive here because **exact terms matter in payments** (a message name, a regulation number) while paraphrases need meaning-based matching.

The plan: keep the 48 questions and the gold-phrase check, swap TF-IDF for embeddings and AI Search, and compare. Because the evaluation is fixed, any change in score is about retrieval, not about a moved goalpost.

---

## 11. Interview check: can you answer these out loud?

1. What is RAG, and what problem does it solve compared with a plain LLM?
2. Walk through a RAG pipeline end to end. Which stage would you measure first, and why separately?
3. What is chunking, and what goes wrong with chunks that are too big or too small?
4. Compare fixed, recursive, semantic and structure-aware chunking. When does each win?
5. What is chunk overlap for, and what does it cost?
6. Why keep the section heading and source metadata on every chunk?
7. Explain TF-IDF and cosine similarity in a few sentences. What is its main limit?
8. Why can a paraphrased question fail with TF-IDF, and how do embeddings help?
9. Define Hit@k and MRR. Why is one question worth 0.023 in your evaluation, and why does that matter?
10. Your first evaluation scored every strategy 100%. What was wrong with it, and how did you fix it?
11. What is a gold phrase, and why check that it exists in the source text?
12. Why can a chunk that lists a question outrank the chunk that answers it? How do you prevent it?
13. Why can't a similarity threshold implement "I don't know"? What would you use instead?
14. A silent bug dropped 80% of a long section. What kind of test catches that?
15. How does BM25 differ from TF-IDF? What do `k1` and `b` control?
16. What does stemming fix, and what can't it fix? Why can it make abstaining harder?
17. You picked a fix after looking at which questions failed. Why is the improvement on those questions optimistic, and what do you do about it?
18. How does an embedding model let a question match a passage that shares no words with it? Where does it fall short?
19. What is reciprocal rank fusion, and why combine keyword and vector search instead of choosing one?
20. Hybrid search improved Hit@3 but not Hit@1 on held-out questions. When does that matter?
21. What is a cross-encoder reranker, and why not use it on the whole corpus?
22. Why can't the retrieval score tell you when to say "I don't know"? What does a reranker do better?
23. Your abstain threshold refused 7 of 12 answerable questions on the test set. Why did it fail to transfer, and how would you choose the threshold given that a wrong answer costs more than a refusal?
24. When a model's answer fails, how do you tell a retrieval problem from a generation problem? What did you find?
25. Your judge model said an answer was fully supported, but it was wrong. How can that happen, and how do you make groundedness measurement more trustworthy?
26. The model followed "cite every claim" for only 78% of sentences. How would you enforce it?

When these feel easy, do the open items under *Still to do* in `notes/week-04.md`: a larger corpus, embeddings, and the grounding rule.
