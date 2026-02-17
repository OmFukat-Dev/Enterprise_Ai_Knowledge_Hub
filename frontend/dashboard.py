# frontend/dashboard.py
import streamlit as st
import requests
import os
import tempfile
import sys
from pathlib import Path
from typing import List

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

DIRECT_MODE = os.getenv("DIRECT_MODE", "0") == "1" or os.getenv("STREAMLIT_ONLY", "0") == "1"

st.set_page_config(page_title="Enterprise AI Knowledge Hub", layout="wide")

API_URL = "http://127.0.0.1:8000/api"
if not DIRECT_MODE:
    try:
        r = requests.get(f"{API_URL}/health", timeout=1)
        if r.status_code != 200:
            DIRECT_MODE = True
    except Exception:
        DIRECT_MODE = True

st.title("Enterprise AI Knowledge Hub")
st.markdown("**Senior/Principal Engineer Project** — Full RAG + MLOps, Zero Cost, Zero Docker")

col1, col2 = st.columns([1, 1])

@st.cache_resource
def _cached_store():
    from src.retrieval.vector_store import get_vector_store
    return get_vector_store()

@st.cache_resource
def _cached_reranker():
    try:
        from sentence_transformers import CrossEncoder
        return CrossEncoder("cross-encoder/ms-marco-MiniLM-L-12-v2")
    except Exception:
        return None

with col1:
    st.header("Upload Document")
    uploaded = st.file_uploader("Drop your PDF here", type="pdf")
    
    if uploaded:
        with st.spinner("Processing PDF..."):
            if DIRECT_MODE:
                from src.ingestion.extract_text import TextExtractor
                from src.ingestion.chunking import semantic_chunk_documents
                extractor = TextExtractor()
                tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
                tmp_file.write(uploaded.getvalue())
                tmp_file.flush()
                tmp = tmp_file.name
                tmp_file.close()
                docs = extractor.extract_from_pdf_advanced(tmp)
                chunks = semantic_chunk_documents(docs)
                store = _cached_store()
                store.add_documents(chunks)
                st.success(f"Success: Ingested {len(chunks)} chunks from {uploaded.name}")
                st.balloons()
                try:
                    os.remove(tmp)
                except Exception:
                    pass
            else:
                files = {"file": (uploaded.name, uploaded.getvalue(), "application/pdf")}
                r = requests.post(f"{API_URL}/upload", files=files)
                if r.status_code == 200:
                    result = r.json()
                    st.success(f"Success: Ingested {result['chunks']} chunks from {uploaded.name}")
                    st.balloons()
                else:
                    st.error(f"Error: {r.text}")

with col2:
    st.header("Ask Questions")
    question = st.text_input("What do you want to know?", placeholder="e.g., What is the conclusion of the thesis?")
    
    if st.button("Get Answer", type="primary") and question:
        with st.spinner("Generating answer..."):
            if DIRECT_MODE:
                from src.generation.llm_integration import generate_answer
                store = _cached_store()
                try:
                    results = store.similarity_search(question, k=8)
                except Exception as e:
                    st.error(f"Search failed: {str(e)}")
                    results = []
                texts: List[str] = [r[0] for r in results] if results else []
                if not texts:
                    st.warning("No relevant chunks found. Please upload documents or refine the question.")
                    st.stop()
                reranker = _cached_reranker()
                if reranker:
                    try:
                        scores = reranker.predict([(question, t) for t in texts])
                        pairs = list(zip(texts, scores))
                        pairs.sort(key=lambda x: x[1], reverse=True)
                        top = [t for t, _ in pairs[:3]]
                        context = "\n\n".join(top)
                    except Exception:
                        context = "\n\n".join(texts[:3])
                else:
                    context = "\n\n".join(texts[:3])
                ans = generate_answer(question, context)
                st.success("Here is your answer:")
                st.markdown(f"{ans}")
                with st.expander("Show retrieved chunks"):
                    st.caption(context[:800] + "...")
            else:
                response = requests.post(
                    f"{API_URL}/ask",
                    data={"question": question},
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                if response.status_code == 200:
                    result = response.json()
                    st.success("Here is your answer:")
                    st.markdown(f"{result['answer']}")
                    if "context_preview" in result:
                        with st.expander("Show retrieved chunks"):
                            st.caption(result["context_preview"])
                else:
                    st.error(f"Error {response.status_code}: {response.text}")

if DIRECT_MODE:
    st.sidebar.success("Running in single-process mode!")
else:
    st.sidebar.success(f"Using backend API: {API_URL}")
st.sidebar.info("Built with:\n- LangChain 0.1.16\n- Groq Llama-3.3-70B\n- Qdrant / PgVector\n- Unstructured + BGE Reranker")
