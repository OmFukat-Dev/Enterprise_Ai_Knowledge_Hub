# app.py — FASTAPI CORE
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, APIRouter
import os
import tempfile
from dotenv import load_dotenv
from src.retrieval.vector_store import get_vector_store
from src.generation.llm_integration import generate_answer

load_dotenv()

app = FastAPI(title="Enterprise AI Knowledge Hub", docs_url="/api/docs", openapi_url="/api/openapi.json")

# Singletons
vector_store = get_vector_store()
reranker = None

router = APIRouter()

@app.get("/health")
async def health():
    return {"status": "healthy", 
            "db_host": os.getenv('DB_HOST', 'not-set'),
            "s3_bucket": os.getenv('S3_BUCKET', 'not-set')}

@app.get("/")
async def hello():
    return {"message": "RAG App API — Use /api/docs for Swagger"}

@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files allowed")
    
    # Save temp file
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, file.filename)
    with open(temp_path, "wb") as f:
        f.write(await file.read())
    
    try:
        # Process with extract_text
        from src.ingestion.extract_text import TextExtractor
        extractor = TextExtractor()
        docs = extractor.extract_from_pdf_advanced(temp_path)
        
        # Chunk
        from src.ingestion.chunking import semantic_chunk_documents
        chunks = semantic_chunk_documents(docs)
        
        # Embed and store
        vector_store.add_documents(chunks)
        
        return {"status": "uploaded", "chunks": len(chunks)}
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

@router.post("/ask")
async def ask_question(question: str = Form(...)):
    results = vector_store.similarity_search(question, k=8)
    candidate_texts = [item[0] for item in results]
    global reranker
    if reranker is None:
        try:
            from sentence_transformers import CrossEncoder
            reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-12-v2")
        except Exception:
            reranker = None
    if reranker:
        scores = reranker.predict([(question, text) for text in candidate_texts])
        pairs = list(zip(candidate_texts, scores))
        pairs.sort(key=lambda x: x[1], reverse=True)
        top = [t for t, _ in pairs[:3]]
        context = "\n\n".join(top)
    else:
        context = "\n\n".join(candidate_texts[:3])
    answer = generate_answer(question, context)
    return {"answer": answer, "context_preview": context[:500] + "..."}

app.include_router(router, prefix="/api")

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
