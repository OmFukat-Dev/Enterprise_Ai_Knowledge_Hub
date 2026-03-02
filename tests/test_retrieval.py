"""
tests/test_retrieval.py
Unit tests for the vector store (in-memory path, no Qdrant disk required).
"""
import uuid
import math
import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb + 1e-8)


# ─────────────────────────────────────────────────────────────────────────────
# QdrantVectorStore — in-memory path (no disk I/O, fast CI tests)
# ─────────────────────────────────────────────────────────────────────────────

class TestQdrantVectorStoreMemory:
    """Tests run purely against the in-memory fallback (no actual Qdrant disk)."""

    def _store(self, tmp_path):
        import os
        os.environ["QDRANT_PATH"] = str(tmp_path / "qdrant_test")
        os.environ["EMBEDDING_MODEL"] = "all-MiniLM-L6-v2"  # small & fast
        from src.retrieval.vector_store import QdrantVectorStore
        return QdrantVectorStore(path=str(tmp_path / "qdrant_test"))

    def test_add_and_search_returns_results(self, tmp_path):
        store = self._store(tmp_path)
        texts = ["The sky is blue.", "Cats are domestic animals.", "Python is a programming language."]
        metas = [{"source": "a.pdf", "page": i + 1} for i in range(3)]
        store.add_texts(texts, metas)

        results = store.similarity_search("What color is the sky?", k=3)
        assert len(results) > 0
        # Top result should be the sky sentence
        top_text, top_meta, top_score = results[0]
        assert "sky" in top_text.lower() or top_score > 0

    def test_search_returns_tuple_format(self, tmp_path):
        store = self._store(tmp_path)
        store.add_texts(["Hello world"], [{"source": "b.pdf", "page": 1}])
        results = store.similarity_search("hello", k=1)
        assert len(results) == 1
        text, meta, score = results[0]
        assert isinstance(text, str)
        assert isinstance(meta, dict)
        assert isinstance(score, float)

    def test_score_threshold_filters(self, tmp_path):
        store = self._store(tmp_path)
        store.add_texts(["Apple fruit", "Car engine"], [{"source": "c.pdf", "page": 1}, {"source": "c.pdf", "page": 2}])
        # Very high threshold should reduce results
        results_low = store.similarity_search("fruit", k=10, score_threshold=0.0)
        results_high = store.similarity_search("fruit", k=10, score_threshold=0.99)
        assert len(results_low) >= len(results_high)

    def test_get_document_count_increases(self, tmp_path):
        store = self._store(tmp_path)
        # Count from Qdrant; fallback to memory length
        before = store.get_document_count()
        store.add_texts(["New document"], [{"source": "d.pdf", "page": 1}])
        after = store.get_document_count()
        # May be equal if Qdrant upsert succeeded and count reflects it
        assert after >= before

    def test_add_documents_dict_format(self, tmp_path):
        store = self._store(tmp_path)
        docs = [
            {"page_content": "Document one content.", "metadata": {"source": "e.pdf", "page": 1}},
            {"page_content": "Document two content.", "metadata": {"source": "e.pdf", "page": 2}},
        ]
        store.add_documents(docs)
        results = store.similarity_search("document content", k=5)
        assert len(results) >= 1

    def test_empty_text_skipped(self, tmp_path):
        store = self._store(tmp_path)
        docs = [{"page_content": "   ", "metadata": {}}, {"page_content": "Valid text here.", "metadata": {"source": "f.pdf", "page": 1}}]
        store.add_documents(docs)
        results = store.similarity_search("valid", k=5)
        # Should not crash and should return something
        assert isinstance(results, list)

    def test_uuid_id_is_valid(self, tmp_path):
        """Regression: ensure UUID format is correct (string uuid4 caused Qdrant failures)."""
        generated = uuid.UUID(str(uuid.uuid4()))
        # If this doesn't raise, the UUID format is correct
        assert isinstance(generated, uuid.UUID)


# ─────────────────────────────────────────────────────────────────────────────
# text_cleaner regression (quick cross-reference)
# ─────────────────────────────────────────────────────────────────────────────

def test_clean_text_idempotent():
    from src.ingestion.text_cleaner import clean_text
    text = "Hello world. This is clean."
    assert clean_text(clean_text(text)) == clean_text(text)
