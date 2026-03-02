"""
src/ingestion/text_cleaner.py
Clean raw PDF/document text before chunking.
"""
import re


def clean_text(text) -> str:
    """
    Apply a series of cleaning steps to raw extracted text.
    Designed to handle common PDF extraction artifacts.

    Steps:
    1. Guard: return "" for None / non-string input
    2. Fix hyphenated line-breaks (e.g., "conclu-\\nding" → "concluding")
    3. Normalize Unicode dashes and quotes to ASCII equivalents
    4. Remove excessive whitespace / blank lines
    5. Strip common PDF header/footer noise (page numbers, "CONFIDENTIAL", etc.)
    6. Normalise multiple spaces within a line to single space
    """
    # ── 1. Guard against None / non-string inputs ─────────────────────────────
    if not text or not isinstance(text, str):
        return ""

    # ── 2. Fix hyphenated line-breaks ────────────────────────────────────────
    # "inter-\noperability" → "interoperability"
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)

    # ── 3. Normalise Unicode punctuation ─────────────────────────────────────
    # Smart quotes → straight quotes
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    # En / em dashes → regular hyphen-dash
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    # Non-breaking space → regular space
    text = text.replace("\u00a0", " ")

    # ── 4. Remove common PDF header/footer patterns ───────────────────────────
    # Lines that are *only* a page number (e.g., "  3  " or "Page 3 of 12")
    text = re.sub(r"(?m)^\s*Page\s+\d+\s+of\s+\d+\s*$", "", text)
    text = re.sub(r"(?m)^\s*\d+\s*$", "", text)
    # Lines that are only dashes/underscores (visual separators)
    text = re.sub(r"(?m)^[-_=]{3,}\s*$", "", text)

    # ── 5. Collapse runs of blank lines → single blank line ──────────────────
    text = re.sub(r"\n{3,}", "\n\n", text)

    # ── 6. Collapse intra-line multiple spaces → single space ─────────────────
    text = re.sub(r"[ \t]{2,}", " ", text)

    # ── 7. Strip leading/trailing whitespace per line ─────────────────────────
    lines = [ln.rstrip() for ln in text.splitlines()]
    text = "\n".join(lines)

    return text.strip()
