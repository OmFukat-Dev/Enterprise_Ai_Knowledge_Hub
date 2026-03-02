
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Global cache for models to avoid redundant loading across threads/calls
_MODELS = {
    "embedding": None,
    "reranker": None
}

def get_embedding_model():
    """Get or load the embedding model singleton."""
    if _MODELS["embedding"] is None:
        from sentence_transformers import SentenceTransformer
        model_name = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")
        logger.info(f"Loading embedding model: {model_name}...")
        _MODELS["embedding"] = SentenceTransformer(model_name)
    return _MODELS["embedding"]

def get_reranker_model():
    """Get or load the reranker model singleton.
    
    The model name is configurable via the RERANKER_MODEL env var,
    defaulting to ms-marco-MiniLM-L-12-v2 (free, local, no API key).
    """
    if _MODELS["reranker"] is None:
        try:
            from sentence_transformers import CrossEncoder
            # Bug Fix: Make reranker model configurable via env var
            model_name = os.getenv(
                "RERANKER_MODEL",
                "cross-encoder/ms-marco-MiniLM-L-12-v2"
            )
            logger.info(f"Loading reranker model: {model_name}...")
            _MODELS["reranker"] = CrossEncoder(model_name)
        except Exception as e:
            logger.error(f"Failed to load reranker: {e}")
            return None
    return _MODELS["reranker"]
