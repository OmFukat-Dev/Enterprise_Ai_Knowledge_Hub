"""
tests/test_ingestion.py
Unit tests for text cleaning and chunking.
No external models needed — pure logic tests.
"""
import pytest


# ─────────────────────────────────────────────────────────────────────────────
# text_cleaner tests
# ─────────────────────────────────────────────────────────────────────────────

class TestCleanText:
    def _clean(self, text):
        from src.ingestion.text_cleaner import clean_text
        return clean_text(text)

    def test_empty_string(self):
        assert self._clean("") == ""

    def test_none_safe(self):
        # Should not crash on None — returns ""
        from src.ingestion.text_cleaner import clean_text
        assert clean_text(None) == ""  # type: ignore

    def test_hyphenated_line_break(self):
        result = self._clean("inter-\noperability is key")
        assert "interoperability" in result
        assert "-\n" not in result

    def test_unicode_quotes_normalized(self):
        result = self._clean("\u201cHello\u201d and \u2018world\u2019")
        assert '"Hello"' in result
        assert "'world'" in result

    def test_page_number_removed(self):
        text = "Content here.\n\n   42   \n\nMore content."
        result = self._clean(text)
        # Bare "42" on its own line should be gone
        for line in result.splitlines():
            assert line.strip() != "42"

    def test_page_x_of_y_removed(self):
        text = "Content\nPage 3 of 10\nMore content"
        result = self._clean(text)
        assert "Page 3 of 10" not in result

    def test_excessive_blank_lines_collapsed(self):
        text = "A\n\n\n\n\nB"
        result = self._clean(text)
        assert "\n\n\n" not in result

    def test_multiple_spaces_collapsed(self):
        text = "word    another    word"
        result = self._clean(text)
        assert "  " not in result


# ─────────────────────────────────────────────────────────────────────────────
# chunking tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSemanticChunkDocuments:
    def _chunk(self, docs, **kwargs):
        from src.ingestion.chunking import semantic_chunk_documents
        return semantic_chunk_documents(docs, **kwargs)

    def test_dict_input_produces_chunks(self):
        docs = [
            {
                "page_content": "This is a test document. " * 100,
                "metadata": {"source": "test.pdf", "page": 1},
            }
        ]
        chunks = self._chunk(docs)
        assert len(chunks) > 0

    def test_chunk_has_required_keys(self):
        docs = [{"page_content": "Hello world. " * 50, "metadata": {"source": "a.pdf", "page": 1}}]
        chunks = self._chunk(docs)
        for c in chunks:
            assert "page_content" in c
            assert "metadata" in c
            assert "chunk_id" in c["metadata"]
            assert "chunk_index" in c["metadata"]
            assert "source" in c["metadata"]

    def test_chunk_id_format(self):
        docs = [{"page_content": "Text. " * 80, "metadata": {"source": "doc.pdf", "page": 2}}]
        chunks = self._chunk(docs)
        for c in chunks:
            cid = c["metadata"]["chunk_id"]
            assert "doc.pdf" in cid
            assert "p2" in cid

    def test_empty_input_returns_empty(self):
        assert self._chunk([]) == []

    def test_empty_page_content_skipped(self):
        docs = [{"page_content": "   ", "metadata": {}}]
        result = self._chunk(docs)
        assert result == []

    def test_chunk_overlap_produces_more_chunks(self):
        long_text = "Sentence number {}. ".format
        text = " ".join(long_text(i) for i in range(200))
        docs = [{"page_content": text, "metadata": {"source": "t.pdf", "page": 1}}]
        chunks_overlap = self._chunk(docs, chunk_size=200, chunk_overlap=50)
        chunks_no_overlap = self._chunk(docs, chunk_size=200, chunk_overlap=0)
        assert len(chunks_overlap) >= len(chunks_no_overlap)

    def test_langchain_document_input_works(self):
        """Make sure LangChain Document objects are also accepted."""
        from langchain_core.documents import Document
        docs = [Document(page_content="Some content. " * 30, metadata={"source": "lc.pdf", "page": 1})]
        chunks = self._chunk(docs)
        assert len(chunks) > 0
