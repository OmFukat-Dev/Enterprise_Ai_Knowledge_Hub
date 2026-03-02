"""
src/ingestion/chunking.py
Semantic-aware chunking with proper LangChain Document conversion and chunk metadata.
"""
import logging
from typing import List, Dict, Any
import os

logger = logging.getLogger(__name__)

# Minimum chunk length — chunks shorter than this are noise (headers, dates, etc.)
MIN_CHUNK_CHARS = int(os.getenv("MIN_CHUNK_CHARS", "50"))


def semantic_chunk_documents(
    documents: list,
    chunk_size: int = int(os.getenv("CHUNK_SIZE", "512")),
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "128")),
) -> List[Dict[str, Any]]:
    """
    Split a list of page documents (dicts OR LangChain Documents) into
    overlapping text chunks suitable for embedding.

    Key behaviours:
    - Converts dicts to langchain_core.documents.Document objects BEFORE
      calling split_documents (raw dicts caused silent crashes in old version).
    - Adds chunk_id + chunk_index to every chunk's metadata.
    - Uses sentence-friendly separators with overlap to preserve context.
    - Skips chunks shorter than MIN_CHUNK_CHARS (noise filtering).
    """
    # ── Normalise input to LangChain Document objects ────────────────────────
    from langchain_core.documents import Document

    lc_docs: List[Document] = []
    for d in documents:
        if isinstance(d, Document):
            lc_docs.append(d)
        elif isinstance(d, dict):
            page_content = d.get("page_content", "")
            metadata = d.get("metadata", {})
            if page_content and page_content.strip():
                lc_docs.append(Document(page_content=page_content, metadata=metadata))
        else:
            text = str(d)
            if text.strip():
                lc_docs.append(Document(page_content=text, metadata={}))

    if not lc_docs:
        return []

    # ── Chunk with RecursiveCharacterTextSplitter ────────────────────────────
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            # Order matters: prefer logical boundaries
            separators=["\n\n", "\n", "---", ". ", "! ", "? ", "; ", ", ", " ", ""],
            keep_separator=True,
            is_separator_regex=False,
        )
        split_docs = splitter.split_documents(lc_docs)
    except Exception as e:
        logger.warning(f"LangChain splitter failed ({e}), using pure-Python fallback.")
        # Pure-Python fallback (no LangChain) — also correct now
        split_docs = _fallback_split(lc_docs, chunk_size, chunk_overlap)

    # ── Add chunk metadata + filter noise chunks ─────────────────────────────
    result: List[Dict[str, Any]] = []
    idx = 0
    for doc in split_docs:
        content = doc.page_content.strip()
        # Bug 15 Fix: Skip very short chunks — they are PDF noise, not content
        if len(content) < MIN_CHUNK_CHARS:
            logger.debug(f"Skipping noise chunk ({len(content)} chars): {content[:40]!r}")
            continue
        meta = dict(doc.metadata)
        meta["chunk_index"] = idx
        # Unique ID combining source + index for deduplication
        source = meta.get("source", "unknown")
        page = meta.get("page", "0")
        meta["chunk_id"] = f"{source}::p{page}::c{idx}"
        result.append({"page_content": content, "metadata": meta})
        idx += 1

    logger.info(f"Chunking produced {len(result)} valid chunks (min_chars={MIN_CHUNK_CHARS}).")
    return result


def _fallback_split(
    docs: list, chunk_size: int, chunk_overlap: int
) -> list:
    """Pure-Python fallback splitter when LangChain is not available."""
    from langchain_core.documents import Document

    chunks = []
    for doc in docs:
        text = doc.page_content
        meta = doc.metadata
        start = 0
        while start < len(text):
            end = min(len(text), start + chunk_size)
            # Try to end on a sentence boundary
            if end < len(text):
                for sep in (". ", ".\n", "\n\n", "\n", " "):
                    pos = text.rfind(sep, start, end)
                    if pos != -1 and pos > start:
                        end = pos + len(sep)
                        break
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(Document(page_content=chunk_text, metadata=meta))
            if end >= len(text):
                break
            start = max(0, end - chunk_overlap)
    return chunks
