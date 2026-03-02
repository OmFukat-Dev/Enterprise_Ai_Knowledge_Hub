"""
src/retrieval/reranker.py
Cross-encoder reranker using a local, free model — no API key required.
"""
import logging
import os

logger = logging.getLogger(__name__)

RERANK_TOP_K = int(os.getenv("RERANK_TOP_K", "5"))


class CrossEncoderReranker:
    """
    Lightweight cross-encoder reranker using a free, locally-run model.
    Scores (query, document) pairs and returns the top-k by relevance.

    Bug 6 Fix: Removed the 'model_name' constructor param that was silently
    ignored. Model loading is now handled exclusively by get_reranker_model()
    (configurable via RERANKER_MODEL env var), keeping a single source of truth.
    """

    def __init__(self):
        from src.retrieval.models import get_reranker_model
        self.model = get_reranker_model()

    def rerank(self, query: str, documents: list, top_k: int = RERANK_TOP_K) -> list:
        """
        Rerank `documents` for `query`. Returns top_k (document, score) pairs.
        Returns [] if model not loaded — caller must handle this with a fallback.
        """
        if not documents or self.model is None:
            logger.warning("Reranker not available or no documents provided; returning empty.")
            return []

        pairs = [(query, doc) for doc in documents]
        scores = self.model.predict(pairs)

        scored = sorted(
            zip(documents, scores),
            key=lambda x: x[1],
            reverse=True,
        )

        # Drop chunks with extremely low relevance
        # Logit -6.0 is very low; loose enough to avoid missing partial info
        scored = [(doc, sc) for doc, sc in scored if sc > -6.0]

        return scored[:top_k]