"""
pipelines/retrieval_pipeline.py
Orchestrates the full retrieval/generation flow:
  expand_query → similarity_search → rerank → generate_answer
"""
import logging
import os
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Bug 1 Fix: All defaults aligned to the .env values (15 for k, 5 for rerank)
RETRIEVAL_K = int(os.getenv("RETRIEVAL_K", "15"))
RERANK_TOP_K = int(os.getenv("RERANK_TOP_K", "5"))
SCORE_THRESHOLD = float(os.getenv("SCORE_THRESHOLD", "0.0"))


def run_retrieval(
    question: str,
    history: Optional[List[Dict[str, str]]] = None,
    store=None,
) -> Dict[str, Any]:
    """
    Run the complete retrieval + generation pipeline.

    Args:
        question: The user's raw question string.
        history:  Prior conversation turns for context.
        store:    Optional pre-initialised vector store (avoids re-loading).

    Returns:
        {
          "answer": str,
          "sources": [{"file": str, "page": int|str}, ...],
          "context_preview": str,
          "chunks_retrieved": int,
        }
    """
    if not question or not question.strip():
        return {
            "answer": "Please provide a question.",
            "sources": [],
            "context_preview": "",
            "chunks_retrieved": 0,
        }

    history = history or []

    # ── Step 1: Multi-query expansion ─────────────────────────────────────────
    from src.generation.llm_integration import expand_query, generate_answer
    queries = expand_query(question)
    logger.info(f"[Retrieval] Expanded to {len(queries)} queries: {queries}")

    # ── Step 2: Similarity search across all query variants ───────────────────
    if store is None:
        from src.retrieval.vector_store import get_vector_store
        store = get_vector_store()

    # Bug 7 Fix: Use a dict for O(1) metadata lookup and to handle duplicate text chunks
    # candidate_texts.index(text) was O(n) and returned the FIRST match
    # (always wrong metadata when overlapping chunks share identical text)
    seen_texts: set = set()
    candidate_texts: List[str] = []
    text_to_meta: Dict[str, dict] = {}  # text → metadata mapping

    for q in queries:
        results = store.similarity_search(q, k=RETRIEVAL_K)
        for text, meta, score in results:
            if text and text not in seen_texts:
                seen_texts.add(text)
                candidate_texts.append(text)
                text_to_meta[text] = meta  # preserves the correct metadata for each unique text

    logger.info(f"[Retrieval] Retrieved {len(candidate_texts)} unique candidate chunks.")

    if not candidate_texts:
        return {
            "answer": (
                "I could not find any relevant information in the uploaded documents. "
                "Please upload a document first, or try rephrasing your question."
            ),
            "sources": [],
            "context_preview": "",
            "chunks_retrieved": 0,
        }

    # ── Step 3: Rerank ────────────────────────────────────────────────────────
    from src.retrieval.reranker import CrossEncoderReranker
    reranker = CrossEncoderReranker()
    scored_results = reranker.rerank(question, candidate_texts, top_k=RERANK_TOP_K)

    # Bug 8 Fix: If reranker returned nothing (model not loaded, or all scores < -6.0),
    # fall back to unranked top-k candidates instead of silently returning an empty answer.
    if scored_results:
        top_texts = [text for text, score in scored_results]
    else:
        logger.warning(
            "[Retrieval] Reranker returned empty results. "
            "Falling back to unranked top-k candidates."
        )
        top_texts = candidate_texts[:RERANK_TOP_K]

    top_meta = [text_to_meta[text] for text in top_texts if text in text_to_meta]

    context = "\n\n---\n\n".join(top_texts)

    # ── Step 4: Collect sources ───────────────────────────────────────────────
    sources = []
    for meta in top_meta:
        entry = {"file": meta.get("source", "unknown"), "page": meta.get("page", "?")}
        if entry not in sources:
            sources.append(entry)

    # ── Step 5: Generate answer ───────────────────────────────────────────────
    answer = generate_answer(question, context, history=history, sources=sources)

    return {
        "answer": answer,
        "sources": sources,
        "context_preview": context[:1000] + ("..." if len(context) > 1000 else ""),
        "chunks_retrieved": len(top_texts),
    }
