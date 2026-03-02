"""
src/generation/llm_integration.py
LLM interaction via local Ollama — no API keys required.
"""
import logging
import os
from pathlib import Path
from typing import List, Optional, Dict, Any

from dotenv import load_dotenv

env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

logger = logging.getLogger(__name__)

# Bug 12 Fix: Consistent default model name (llama3) across all files
MODEL = os.getenv("LLM_MODEL", "llama3")
TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))
MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "2048"))
NUM_CTX = int(os.getenv("LLM_NUM_CTX", "8192"))
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
# Stability-first default: run CPU unless explicitly overridden.
# Set OLLAMA_NUM_GPU=1 (or higher) if your system is stable on GPU.
OLLAMA_NUM_GPU = int(os.getenv("OLLAMA_NUM_GPU", "0"))
FALLBACK_NUM_CTX = int(os.getenv("LLM_FALLBACK_NUM_CTX", "4096"))
FALLBACK_MAX_TOKENS = int(os.getenv("LLM_FALLBACK_MAX_TOKENS", "1024"))
LOW_MEM_FALLBACK_MODEL = os.getenv("LLM_LOW_MEM_FALLBACK_MODEL", "llama3.2:1b")

# Global flag: if a CUDA error occurs, all subsequent calls auto-use CPU
_FORCE_CPU_MODE = False


# ── System Prompt ─────────────────────────────────────────────────────────────
_SYSTEM_PROMPT_TEMPLATE = """\
You are an expert Enterprise AI Document Analysis Assistant.
Your goal is to provide a comprehensive, accurate, and perfectly grounded answer based ONLY on the provided DOCUMENT CONTEXT.

STRICT OPERATIONAL GUIDELINES:
1. **Groundedness**: Use ONLY the information from the DOCUMENT CONTEXT. Do not use external knowledge.
2. **Precision**: If the answer is present, be thorough and include specific details (dates, names, metrics).
3. **Transparency**: If the context does not contain enough information to answer fully, explicitly state:
   "The provided documents do not contain information about [X], but they do mention [Y]."
4. **No Hallucination**: If the answer is entirely missing, respond EXACTLY with:
   "I cannot find this information in the provided document."
5. **Formatting**: Use markdown (bullet points, bold text) for readability.
6. **Citations**: ALWAYS end your response with a "Sources" section listing the filenames and pages used.

--- DOCUMENT CONTEXT ---
{context}

--- METADATA ---
{sources}

--- INSTRUCTIONS ---
Based on the context and metadata above, answer the user's question. If multiple documents are provided, synthesize the information across them.
"""


def _build_messages(
    question: str,
    context: str,
    history: Optional[List[Dict[str, str]]] = None,
    sources: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, str]]:
    """Build an Ollama-compatible message list with history support."""
    formatted_sources = ""
    if sources:
        formatted_sources = "\n".join([f"- File: {s['file']}, Page: {s['page']}" for s in sources])
    else:
        formatted_sources = "No metadata provided."

    system_content = _SYSTEM_PROMPT_TEMPLATE.format(context=context, sources=formatted_sources)
    messages: List[Dict[str, str]] = [{"role": "system", "content": system_content}]

    if history:
        # Only pass the last 6 turns to avoid inflating the context window
        for turn in history[-6:]:
            if turn.get("role") in ("user", "assistant") and turn.get("content"):
                messages.append(turn)

    messages.append({"role": "user", "content": question})
    return messages


def _get_ollama_client():
    """Return an Ollama client pointing at the configured host."""
    import ollama  # type: ignore
    return ollama.Client(host=OLLAMA_HOST)


def _chat_with_fallback(client, model, messages, options):
    """Try to chat, falling back to CPU-only if a CUDA error occurs."""
    global _FORCE_CPU_MODE

    # Prefer explicit runtime setting; if OLLAMA_NUM_GPU=0 use CPU from the start.
    options_base = options.copy()
    if _FORCE_CPU_MODE or OLLAMA_NUM_GPU == 0:
        options_base["num_gpu"] = 0
    else:
        options_base["num_gpu"] = OLLAMA_NUM_GPU

    try:
        return client.chat(model=model, messages=messages, options=options_base)
    except Exception as e:
        err_msg = str(e).lower()
        is_cuda_err = "cuda error" in err_msg or "gpu" in err_msg or "terminated" in err_msg

        if is_cuda_err:
            logger.debug(f"CUDA/500 error detected: {err_msg}. Enabling persistent CPU mode.")
            _FORCE_CPU_MODE = True
            options_cpu = options.copy()
            options_cpu["num_gpu"] = 0
            try:
                logger.debug("Retrying with CPU mode...")
                return client.chat(model=model, messages=messages, options=options_cpu)
            except Exception as e2:
                raise e2
        raise e


def _extract_message_content(response) -> str:
    """Support both dict and ollama ChatResponse objects."""
    if isinstance(response, dict):
        return (response.get("message", {}) or {}).get("content", "").strip()
    message = getattr(response, "message", None)
    if message is None:
        return ""
    content = getattr(message, "content", "")
    return (content or "").strip()


def _is_memory_error(err_msg: str) -> bool:
    return (
        "requires more system memory" in err_msg
        or "out of memory" in err_msg
        or "not enough memory" in err_msg
    )


def expand_query(question: str) -> List[str]:
    """
    Generate 2 alternative phrasings of the question to improve retrieval recall.
    Falls back to [question] on any error (model not running, etc.).
    """
    prompt = (
        "Generate exactly 2 alternative phrasings of the following search question "
        "that would help retrieve relevant document sections. "
        "Return only the 2 questions — one per line — with no numbering, bullets, or extra text.\n\n"
        f"Original question: {question}"
    )
    try:
        client = _get_ollama_client()
        response = _chat_with_fallback(
            client=client,
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.4, "num_predict": 128, "num_ctx": 512},
        )
        raw = _extract_message_content(response)
        alternatives = [q.strip() for q in raw.splitlines() if q.strip()]
        # Deduplicate while preserving order
        seen = {question.lower()}
        unique = [question]
        for alt in alternatives[:2]:
            if alt.lower() not in seen:
                seen.add(alt.lower())
                unique.append(alt)
        return unique
    except Exception as e:
        logger.debug(f"expand_query failed (Ollama may not be running): {e}")
        return [question]


def generate_answer(
    question: str,
    context: str,
    history: Optional[List[Dict[str, str]]] = None,
    sources: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """
    Generate a grounded answer using only the provided document context.

    Args:
        question: The user's question.
        context:  Concatenated retrieved document chunks (already reranked).
        history:  Optional prior chat turns [{"role": ..., "content": ...}].

    Returns:
        Answer string from the LLM, or a structured error message.
    """
    if not context or not context.strip():
        return (
            "I could not find any relevant information in the uploaded documents "
            "to answer your question. Please make sure you have uploaded a document "
            "and try rephrasing your question."
        )

    try:
        client = _get_ollama_client()
    except ImportError:
        return (
            "⚠️ The `ollama` Python package is not installed. "
            "Run: `pip install -r requirements.txt` to fix this."
        )

    messages = _build_messages(question, context, history, sources)

    try:
        response = _chat_with_fallback(
            client=client,
            model=MODEL,
            messages=messages,
            options={
                "temperature": TEMPERATURE,
                "num_predict": MAX_TOKENS,
                "num_ctx": NUM_CTX,
            },
        )
        answer = _extract_message_content(response)
        return answer if answer else "The model returned an empty response. Please try again."

    except Exception as e:
        err = str(e).lower()
        if _is_memory_error(err):
            # Retry with a smaller model if available locally.
            try:
                response = client.chat(
                    model=LOW_MEM_FALLBACK_MODEL,
                    messages=messages,
                    options={
                        "temperature": TEMPERATURE,
                        "num_predict": min(MAX_TOKENS, FALLBACK_MAX_TOKENS),
                        "num_ctx": min(NUM_CTX, FALLBACK_NUM_CTX),
                        "num_gpu": 0,
                    },
                )
                answer = _extract_message_content(response)
                if answer:
                    return answer
            except Exception:
                pass
            return (
                "⚠️ **Insufficient System Memory for Current Model**\n\n"
                f"Configured model `{MODEL}` cannot run with available RAM.\n\n"
                "**Fix:**\n"
                f"1. Pull a smaller model: `ollama pull {LOW_MEM_FALLBACK_MODEL}`\n"
                f"2. Set `LLM_MODEL={LOW_MEM_FALLBACK_MODEL}` in `.env`\n"
                "3. Restart backend and retry."
            )
        if "cuda error" in err or "gpu" in err or "terminated" in err:
            # Last-chance stable retry with lower memory footprint on CPU.
            try:
                global _FORCE_CPU_MODE
                _FORCE_CPU_MODE = True
                slim_messages = _build_messages(
                    question=question,
                    context=context[:6000],
                    history=(history or [])[-2:],
                    sources=sources,
                )
                response = client.chat(
                    model=MODEL,
                    messages=slim_messages,
                    options={
                        "temperature": TEMPERATURE,
                        "num_predict": min(MAX_TOKENS, FALLBACK_MAX_TOKENS),
                        "num_ctx": min(NUM_CTX, FALLBACK_NUM_CTX),
                        "num_gpu": 0,
                    },
                )
                answer = _extract_message_content(response)
                if answer:
                    return answer
            except Exception:
                pass
            return (
                "⚠️ **Ollama GPU Failure**\n\n"
                "Your graphics card (GPU) crashed and the automatic CPU fallback "
                "could not recover. This often happens when another app is using "
                "too much video memory (VRAM).\n\n"
                "**To fix this:**\n"
                "1. Restart the Ollama application.\n"
                "2. Close high-VRAM apps (games, video editing tools) and retry.\n"
                "3. Force CPU mode permanently: set `OLLAMA_NUM_GPU=0` in `.env` and restart backend."
            )
        if "connection refused" in err or "connect" in err or "timeout" in err:
            return (
                f"⚠️ **Ollama is not running.**\n\n"
                f"To fix this:\n"
                f"1. Open a terminal and run: `ollama serve`\n"
                f"2. Make sure the model is downloaded: `ollama pull {MODEL}`\n"
                f"3. Then retry your question.\n\n"
                f"_(Technical detail: {e})_"
            )
        if "model" in err and ("not found" in err or "unknown" in err):
            return (
                f"⚠️ **Model `{MODEL}` not found in Ollama.**\n\n"
                f"Download it by running: `ollama pull {MODEL}`\n"
                f"Then retry your question."
            )
        return (
            f"⚠️ Error generating answer: {e}\n\n"
            f"Make sure Ollama is running (`ollama serve`) and "
            f"the model is available (`ollama pull {MODEL}`)."
        )
