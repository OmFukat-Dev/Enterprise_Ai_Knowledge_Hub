import os
import sys
import tempfile
from pathlib import Path
from typing import List, Dict

import requests
import streamlit as st

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from dotenv import load_dotenv
load_dotenv(dotenv_path=_root / ".env")

# ── Configuration ─────────────────────────────────────────────────────────
# Bug 11 Fix: DIRECT_MODE detection moved after dotenv load so env vars are available
DIRECT_MODE = os.getenv("DIRECT_MODE", "0") == "1" or os.getenv("STREAMLIT_ONLY", "1") == "1"
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000/api")
RERANK_TOP_K = int(os.getenv("RERANK_TOP_K", "5"))
RETRIEVAL_K = int(os.getenv("RETRIEVAL_K", "15"))
SCORE_THRESHOLD = float(os.getenv("SCORE_THRESHOLD", "0.0"))

# ── Page config ───────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Enterprise AI Knowledge Hub",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .answer-container {
        background: #f0f7ff;
        border-left: 4px solid #1f77b4;
        padding: 1rem 1.2rem;
        border-radius: 6px;
        margin-top: 0.5rem;
    }
    .source-chip {
        display: inline-block;
        background: #e8f4ea;
        border: 1px solid #4caf50;
        border-radius: 12px;
        padding: 2px 10px;
        font-size: 0.8rem;
        margin: 2px 3px;
        color: #256029;
    }
    .chat-user {
        background: #e3f2fd;
        color: #0d47a1 !important;
        border-radius: 10px;
        padding: 8px 12px;
        margin: 4px 0;
        font-weight: 500;
    }
    .chat-bot {
        background: #f1f8e9;
        color: #1b5e20 !important;
        border-radius: 10px;
        padding: 8px 12px;
        margin: 4px 0;
        font-weight: 500;
    }
</style>
""", unsafe_allow_html=True)

# ── API availability check ─────────────────────────────────────────────────
if not DIRECT_MODE:
    try:
        r = requests.get(f"{API_URL}/health", timeout=2)
        DIRECT_MODE = r.status_code != 200
    except Exception:
        DIRECT_MODE = True

# ── Session state init ─────────────────────────────────────────────────────
if "chat_history" not in st.session_state:
    st.session_state.chat_history: List[Dict[str, str]] = []
if "documents_indexed" not in st.session_state:
    st.session_state.documents_indexed: List[str] = []


# ── Cached resources ────────────────────────────────────────────────────────
@st.cache_resource
def _cached_store():
    from src.retrieval.vector_store import get_vector_store
    return get_vector_store()


@st.cache_resource
def _cached_reranker():
    from src.retrieval.models import get_reranker_model
    return get_reranker_model()


# ── Header ─────────────────────────────────────────────────────────────────
st.title("🧠 Enterprise AI Knowledge Hub")
st.caption("Upload your documents, then ask anything — powered by local LLM, 100% free & private.")

col_upload, col_chat = st.columns([1, 2], gap="large")


# ── Upload panel ────────────────────────────────────────────────────────────
with col_upload:
    st.subheader("📂 Upload Documents")
    uploaded = st.file_uploader(
        "Drop a PDF, DOCX, or TXT file",
        type=["pdf", "docx", "txt"],
        help="The document will be chunked and indexed into the vector store.",
    )

    if uploaded:
        if uploaded.name not in st.session_state.documents_indexed:
            with st.spinner(f"Indexing **{uploaded.name}**..."):
                if DIRECT_MODE:
                    from pipelines.ingestion_pipeline import run_ingestion

                    tmp_file = tempfile.NamedTemporaryFile(
                        delete=False, suffix=os.path.splitext(uploaded.name)[-1]
                    )
                    tmp_file.write(uploaded.getvalue())
                    tmp_file.flush()
                    tmp = tmp_file.name
                    tmp_file.close()

                    result = run_ingestion(tmp, store=_cached_store())
                    try:
                        os.remove(tmp)
                    except Exception:
                        pass

                    if result["status"] == "success" and result["chunks_indexed"] > 0:
                        st.session_state.documents_indexed.append(uploaded.name)
                        st.success(
                            f"✅ Indexed **{result['chunks_indexed']}** chunks from `{uploaded.name}`"
                        )
                        st.balloons()
                    else:
                        st.error(f"❌ {result.get('error', 'Could not extract text.')}")
                else:
                    files = {"file": (uploaded.name, uploaded.getvalue(), "application/octet-stream")}
                    r = requests.post(f"{API_URL}/upload", files=files)
                    if r.status_code == 200:
                        result = r.json()
                        st.session_state.documents_indexed.append(uploaded.name)
                        st.success(
                            f"✅ Indexed **{result.get('chunks_indexed', '?')}** chunks "
                            f"from `{uploaded.name}`"
                        )
                        st.balloons()
                    else:
                        st.error(f"❌ Upload failed: {r.text}")
        else:
            st.info(f"`{uploaded.name}` is already indexed.")

    if st.session_state.documents_indexed:
        st.markdown("**Indexed documents:**")
        for name in st.session_state.documents_indexed:
            st.markdown(f"- 📄 `{name}`")

    st.divider()
    st.markdown("**ℹ️ Requirements**")
    st.markdown(
        "- Ollama must be running: `ollama serve`\n"
        f"- Model must be pulled: `ollama pull {os.getenv('LLM_MODEL', 'llama3')}`"
    )


# ── Chat panel ──────────────────────────────────────────────────────────────
with col_chat:
    st.subheader("💬 Ask Questions")

    # Show chat history
    for turn in st.session_state.chat_history:
        if turn["role"] == "user":
            st.markdown(
                f'<div class="chat-user">🧑 <b>You:</b> {turn["content"]}</div>',
                unsafe_allow_html=True,
            )
        else:
            # Bot responses use st.markdown for proper markdown rendering (not raw HTML injection)
            with st.container():
                st.markdown(
                    '<div class="chat-bot">🤖 <b>Assistant:</b></div>',
                    unsafe_allow_html=True,
                )
                st.markdown(turn["content"])

    question = st.text_input(
        "Your question",
        placeholder="e.g., What are the main conclusions of the document?",
        label_visibility="collapsed",
    )

    btn_col, clear_col = st.columns([3, 1])
    with btn_col:
        ask_btn = st.button("🔍 Get Answer", type="primary", use_container_width=True)
    with clear_col:
        if st.button("🗑️ Clear History", use_container_width=True):
            st.session_state.chat_history = []
            st.rerun()

    if ask_btn and question and question.strip():
        with st.spinner("Searching documents and generating answer..."):
            if DIRECT_MODE:
                from pipelines.retrieval_pipeline import run_retrieval

                result = run_retrieval(
                    question,
                    history=st.session_state.chat_history,
                    store=_cached_store(),
                )
                ans = result["answer"]
                sources = result["sources"]
                top_texts = [result["context_preview"]]

            else:
                payload = {
                    "question": question,
                    "history": st.session_state.chat_history,
                }
                response = requests.post(f"{API_URL}/ask", json=payload)
                if response.status_code == 200:
                    result = response.json()
                    ans = result.get("answer", "No answer returned.")
                    sources = result.get("sources", [])
                    context = result.get("context_preview", "")
                    top_texts = [context]
                else:
                    st.error(f"API Error {response.status_code}: {response.text}")
                    st.stop()

            # ── Update history ──────────────────────────────────────────
            st.session_state.chat_history.append({"role": "user", "content": question})
            st.session_state.chat_history.append({"role": "assistant", "content": ans})

            # ── Display answer ──────────────────────────────────────────
            # Bug 11 Fix: Use st.container + st.markdown instead of raw HTML injection.
            # This renders markdown (bold, bullet lists, code blocks) from LLM responses correctly.
            st.markdown("**Answer:**")
            with st.container():
                st.markdown('<div class="answer-container">', unsafe_allow_html=True)
                st.markdown(ans)
                st.markdown('</div>', unsafe_allow_html=True)

            # ── Sources ─────────────────────────────────────────────────
            if sources:
                st.markdown("**Sources:**")
                chips = "".join(
                    f'<span class="source-chip">📄 {s["file"]} — page {s["page"]}</span>'
                    for s in sources
                )
                st.markdown(chips, unsafe_allow_html=True)

            # ── Context preview ─────────────────────────────────────────
            with st.expander("🔍 Show retrieved context chunks"):
                preview = "\n\n---\n\n".join(top_texts)
                st.caption(preview[:1500] + ("..." if len(preview) > 1500 else ""))

            st.rerun()

    elif ask_btn and not question.strip():
        st.warning("Please enter a question.")


# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("System Info")

    mode_label = "🟢 Single-process mode" if DIRECT_MODE else f"🔵 Backend API: `{API_URL}`"
    st.success(mode_label)

    # Show vector store document count
    try:
        store = _cached_store()
        doc_count = store.get_document_count()
        st.metric("Vectors indexed", doc_count)
    except Exception:
        pass

    st.markdown("---")
    st.markdown("**Stack (all free)**")
    st.markdown(
        "- 🤖 Ollama (local LLM)\n"
        "- 🧬 BAAI/bge-large-en-v1.5 (embeddings)\n"
        "- 🔎 ms-marco CrossEncoder (reranker)\n"
        "- 🗄️ Qdrant local (vector DB)\n"
        "- 🖥️ FastAPI + Streamlit\n"
    )
    st.markdown("---")
    st.markdown("**Retrieval Settings**")
    st.markdown(
        f"- Retrieval k: `{RETRIEVAL_K}`\n"
        f"- Rerank top-k: `{RERANK_TOP_K}`\n"
        f"- Score threshold: `{SCORE_THRESHOLD}`\n"
        f"- Model: `{os.getenv('LLM_MODEL', 'llama3')}`\n"
        f"- Context window: `{os.getenv('LLM_NUM_CTX', '8192')} tokens`"
    )
