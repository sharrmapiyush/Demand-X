"""Local RAG assistant — deterministic evidence-grounded retrieval and generation.

Provides keyword-based retrieval from persisted observations and template-based
answer generation (no external LLM required for MVP).
"""

from ai.rag.engine import LocalRAGEngine, RAGRecord

__all__ = ["LocalRAGEngine", "RAGRecord"]