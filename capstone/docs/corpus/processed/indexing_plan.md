# Corpus indexing and chunking plan

## Goal

Convert the public payments corpus into clean retrieval-ready chunks that can be embedded and indexed
for a RAG pipeline.

## Source material status

The current corpus includes public summaries for:

- ISO 20022 overview
- card scheme payment lifecycle
- RBI public payment-system guidance
- a starter FAQ file

## Proposed workflow

1. Clean markdown files
   - normalize headings
   - remove duplicate whitespace
   - keep section boundaries
   - retain source metadata

2. Build a document registry
   - each document gets an ID, title, source, jurisdiction, and raw path
   - store in a JSON/CSV manifest for indexing

3. Chunk each document with four strategies
   - fixed-size chunking
   - recursive chunking
   - semantic chunking
   - structure-aware chunking

4. Attach metadata to every chunk
   - document_id
   - source_title
   - section_heading
   - chunk_index
   - source_url
   - chunk_strategy

5. Embed and index the chunks
   - use a simple vector store or local in-memory index first
   - keep metadata alongside vectors
   - store retrieval results with source references

6. Evaluate retrieval quality
   - ask a small set of questions
   - check whether the top-k chunks contain the correct source information
   - score relevance and groundedness

## Example questions for the first pass

- What is the difference between authorization and settlement?
- What is ISO 20022 used for?
- Why is strong customer authentication important in digital payments?
- How do card schemes and banks interact in the payment lifecycle?
- What kinds of risk controls are discussed in public payment guidance?

## Success criteria for the first version

- Each chunk contains a coherent concept or rule.
- Section headings remain visible in the chunk content.
- Retrieval ranks the right document or section near the top.
- Source references are preserved in the answer pipeline.
