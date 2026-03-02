from functools import lru_cache
import os
import tempfile
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, File, Form, HTTPException, UploadFile, Body
from pydantic import BaseModel

from src.retrieval.vector_store import get_vector_store

load_dotenv()

# ── Configuration from env ──────────────────────────────────────────────────
RETRIEVAL_K = int(os.getenv("RETRIEVAL_K", "15"))
RERANK_TOP_K = int(os.getenv("RERANK_TOP_K", "5"))
SCORE_THRESHOLD = float(os.getenv("SCORE_THRESHOLD", "0.25"))

# ── FastAPI setup ────────────────────────────────────────────────────────────
app = FastAPI(
    title="Enterprise AI Knowledge Hub",
    description="Local RAG system — 100% free, zero cloud dependencies.",
    version="2.0.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)
router = APIRouter()
_reranker = None


@lru_cache()
def _vector_store():
    return get_vector_store()


def _get_reranker():
    global _reranker
    if _reranker is None:
        try:
            from sentence_transformers import CrossEncoder
            _reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-12-v2")
        except Exception:
            _reranker = None
    return _reranker


@app.get("/health")
async def health_root():
    return {
        "status": "healthy",
        "vector_store": os.getenv("VECTOR_STORE_TYPE", "qdrant"),
        "llm_model": os.getenv("LLM_MODEL", "llama3"),
        "retrieval_k": RETRIEVAL_K,
        "rerank_top_k": RERANK_TOP_K,
        "score_threshold": SCORE_THRESHOLD,
    }

@router.get("/health")
async def health_api():
    return {
        "status": "healthy",
        "vector_store": os.getenv("VECTOR_STORE_TYPE", "qdrant"),
        "llm_model": os.getenv("LLM_MODEL", "llama3"),
        "retrieval_k": RETRIEVAL_K,
        "rerank_top_k": RERANK_TOP_K,
        "score_threshold": SCORE_THRESHOLD,
    }


# ── Debug ─────────────────────────────────────────────────────────────────────
@router.get("/debug")
async def debug_info():
    """Diagnostics: how many vectors are stored and what models are active."""
    store = _vector_store()
    try:
        doc_count = store.get_document_count()
    except Exception:
        doc_count = len(getattr(store, '_memory', []))
    return {
        "qdrant_path": os.getenv("QDRANT_PATH", "./data/qdrant_db"),
        "collection": os.getenv("QDRANT_COLLECTION", "enterprise_knowledge"),
        "documents_indexed": doc_count,
        "embedding_model": os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5"),
        "llm_model": os.getenv("LLM_MODEL", "llama3"),
        "num_ctx": int(os.getenv("LLM_NUM_CTX", "8192")),
        "score_threshold": SCORE_THRESHOLD,
    }


@app.get("/")
async def hello():
    return {"message": "Enterprise AI Knowledge Hub API — visit /api/docs for Swagger UI"}


# ── Upload ────────────────────────────────────────────────────────────────────
@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    allowed = {".pdf", ".docx", ".txt"}
    ext = os.path.splitext(file.filename or "")[-1].lower()
    if ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' is not supported. Allowed: {', '.join(allowed)}"
        )

    temp_path = os.path.join(tempfile.gettempdir(), file.filename)
    with open(temp_path, "wb") as f:
        f.write(await file.read())

    try:
        from pipelines.ingestion_pipeline import run_ingestion
        result = run_ingestion(temp_path)
        if result["status"] == "error":
            raise HTTPException(status_code=422, detail=result["error"])
        return {
            "status": "success",
            "filename": result["filename"],
            "chunks_indexed": result["chunks_indexed"],
        }
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


# ── Ask ───────────────────────────────────────────────────────────────────────
class AskRequest(BaseModel):
    question: str
    history: Optional[List[dict]] = None


@router.post("/ask")
async def ask_question(
    payload: Optional[AskRequest] = Body(None),
    question: Optional[str] = Form(None),
):
    """
    Answer a question based on indexed documents.
    Accepts JSON body (preferred) or form-data 'question'.
    """
    if payload is not None and getattr(payload, "question", None):
        q = payload.question
        history = payload.history or []
    elif question:
        q = question
        history = []
    else:
        raise HTTPException(status_code=422, detail="'question' is required.")

    if not q or not q.strip():
        raise HTTPException(status_code=422, detail="Question cannot be empty.")

    # ── Delegate to retrieval pipeline ───────────────────────────────────────
    from pipelines.retrieval_pipeline import run_retrieval
    result = run_retrieval(q, history=history, store=_vector_store())
    return {
        "answer": result["answer"],
        "sources": result["sources"],
        "context_preview": result["context_preview"],
        "chunks_retrieved": result.get("chunks_retrieved", 0),
    }


app.include_router(router, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
