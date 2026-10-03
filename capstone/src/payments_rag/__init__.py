"""Capstone: RAG assistant over a banking/payments knowledge base on Azure (from Week 4)."""

from .azure_clients import (
    AzureChatGenerator,
    AzureHybridRetriever,
    AzureOpenAIEmbedder,
    AzureSearchStore,
    AzureSettings,
)
from .chunking import (
    STRATEGIES,
    Chunk,
    chunk_document,
    chunk_text,
    chunk_text_recursive,
    chunk_text_semantic,
    chunk_text_structure_aware,
    compare_chunking_strategies,
    strip_sections,
)
from .embeddings import Embedder, SentenceTransformerEmbedder
from .grounding import (
    NO_ANSWER,
    Answerability,
    CitedReply,
    GroundedAnswer,
    answerability_prompt,
    build_prompt,
    choose_threshold,
    enforce_citations,
    parse_answerability,
    retrieve_evidence,
    split_sentences,
)
from .reranking import CrossEncoderReranker, Reranker, rerank
from .retrieval import METHODS, Hit, Retriever, build_retriever, retrieve_chunks

__version__ = "0.1.0"

__all__ = [
    "NO_ANSWER",
    "METHODS",
    "STRATEGIES",
    "AzureChatGenerator",
    "AzureHybridRetriever",
    "AzureOpenAIEmbedder",
    "AzureSearchStore",
    "AzureSettings",
    "Chunk",
    "Answerability",
    "answerability_prompt",
    "parse_answerability",
    "CitedReply",
    "Embedder",
    "Reranker",
    "GroundedAnswer",
    "CrossEncoderReranker",
    "Hit",
    "Retriever",
    "SentenceTransformerEmbedder",
    "__version__",
    "build_retriever",
    "retrieve_evidence",
    "rerank",
    "choose_threshold",
    "build_prompt",
    "enforce_citations",
    "split_sentences",
    "chunk_document",
    "chunk_text",
    "chunk_text_recursive",
    "chunk_text_semantic",
    "chunk_text_structure_aware",
    "compare_chunking_strategies",
    "retrieve_chunks",
    "strip_sections",
]
