import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def run_ingestion(file_path: str, store=None) -> Dict[str, Any]:
    """
    Run the complete ingestion pipeline for a single file.

    Args:
        file_path: Absolute path to the PDF/DOCX/TXT file on disk.
        store:     Optional pre-initialised vector store. Pass the
                   Streamlit-cached store here to avoid Qdrant file-lock
                   conflicts between multiple QdrantClient instances.

    Returns:
        {
          "status": "success" | "error",
          "filename": str,
          "chunks_indexed": int,
          "error": str | None
        }
    """
    filename = os.path.basename(file_path)
    logger.info(f"[Ingestion] Starting: {filename}")

    # ── Step 1: Extract text ──────────────────────────────────────────────────
    from src.ingestion.extract_text import TextExtractor
    extractor = TextExtractor()
    ext = os.path.splitext(filename)[-1].lower()

    try:
        if ext == ".pdf":
            docs = extractor.extract_from_pdf_advanced(file_path)
        elif ext in (".docx", ".doc"):
            docs = extractor.extract_from_docx(file_path)
        else:
            # Plain text
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
            from src.ingestion.text_cleaner import clean_text
            docs = [{"page_content": clean_text(text), "metadata": {"source": filename, "page": 1}}]
    except Exception as e:
        logger.error(f"[Ingestion] Extraction failed: {e}")
        return {"status": "error", "filename": filename, "chunks_indexed": 0, "error": str(e)}

    if not docs:
        return {
            "status": "error",
            "filename": filename,
            "chunks_indexed": 0,
            "error": "No text could be extracted. The file may be image-only or corrupt.",
        }

    logger.info(f"[Ingestion] Extracted {len(docs)} pages from {filename}")

    # ── Step 2: Chunk ─────────────────────────────────────────────────────────
    from src.ingestion.chunking import semantic_chunk_documents
    chunks = semantic_chunk_documents(docs)

    if not chunks:
        return {
            "status": "error",
            "filename": filename,
            "chunks_indexed": 0,
            "error": "Chunking produced no results. Text may be too short.",
        }

    logger.info(f"[Ingestion] Produced {len(chunks)} chunks.")

    # ── Step 3: Store in vector DB ────────────────────────────────────────────
    # Use the provided store if available (avoids Qdrant file-lock conflict
    # when Streamlit already holds the lock via _cached_store()).
    if store is None:
        from src.retrieval.vector_store import get_vector_store
        store = get_vector_store()
    store.add_documents(chunks)

    logger.info(f"[Ingestion] Indexed {len(chunks)} chunks from {filename}.")
    return {
        "status": "success",
        "filename": filename,
        "chunks_indexed": len(chunks),
        "error": None,
    }
