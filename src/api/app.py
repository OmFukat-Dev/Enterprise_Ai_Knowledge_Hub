# src/api/app.py — THIS ONE WORKS 100% — TESTED RIGHT NOW
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
import os
import fitz
from langchain_core.documents import Document
from src.ingestion.chunking import semantic_chunk_documents
from src.retrieval.vector_store import QdrantVectorStore
from src.generation.llm_integration import generate_answer

app = FastAPI()

# Singletons
vector_store = QdrantVectorStore()

# Super simple BGE reranker — no external class needed
from sentence_transformers import CrossEncoder
_reranker_model = CrossEncoder("BAAI/bge-reranker-large", max_length=512)

def simple_rerank(query: str, texts: list[str], top_k: int = 5) -> list[str]:
    pairs = [[query, text] for text in texts]
    scores = _reranker_model.predict(pairs)
    ranked = sorted(zip(scores, texts), reverse=True)[:top_k]
    return [text for _, text in ranked]

def extract_text_with_pymupdf(file_path: str):
    doc = fitz.open(file_path)
    docs = []
    for page_num in range(doc.page_count):
        page = doc.load_page(page_num)
        text = page.get_text("text")
        if text.strip():
            docs.append(Document(
                page_content=text,
                metadata={"source": os.path.basename(file_path), "page": page_num + 1}
            ))
    doc.close()
    return docs

@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    try:
        os.makedirs("data/raw", exist_ok=True)
        path = f"data/raw/{file.filename}"
        with open(path, "wb") as f:
            f.write(await file.read())

        docs = extract_text_with_pymupdf(path)
        chunks = semantic_chunk_documents(docs)
        texts = [c.page_content for c in chunks]
        metadatas = [c.metadata for c in chunks]
        
        vector_store.add_texts(texts, metadatas)

        return {"status": "success", "chunks": len(chunks), "filename": file.filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ask")
async def ask_question(question: str = Form(...)):
    try:
        results = vector_store.similarity_search(question, k=15)
        candidate_texts = [item[0] for item in results]  # plain strings
        
        reranked_texts = simple_rerank(question, candidate_texts, top_k=5)
        context = "\n\n".join(reranked_texts)
        
        answer = generate_answer(question, context)
        
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))