import os
from typing import List

class TextExtractor:
    def __init__(self):
        pass

    def extract_from_pdf_advanced(self, pdf_path: str) -> List[dict]:
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        try:
            import fitz
            doc = fitz.open(pdf_path)
            docs = []
            for i, page in enumerate(doc):
                text = page.get_text()
                if text.strip():
                    docs.append({
                        "page_content": text.strip(),
                        "metadata": {"type": "text", "source": os.path.basename(pdf_path), "page": i+1}
                    })
            doc.close()
            if docs:
                return docs
            # If PyMuPDF extracted no text (likely scanned PDF), try OCR fallback
            return self._ocr_fallback(pdf_path)
        except Exception as e:
            # print(f"Error extracting text: {e}")
            return []

    def _ocr_fallback(self, pdf_path: str) -> List[dict]:
        """Attempt OCR on each page if no text was extracted."""
        try:
            import fitz
            from PIL import Image
            import pytesseract
        except Exception:
            # OCR dependencies not available
            return []
        # Try to set tesseract binary if common Windows path exists
        try:
            import shutil as _sh
            if _sh.which("tesseract") is None:
                candidate = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
                if os.path.exists(candidate):
                    pytesseract.pytesseract.tesseract_cmd = candidate
        except Exception:
            pass
        docs: List[dict] = []
        try:
            doc = fitz.open(pdf_path)
            for i, page in enumerate(doc):
                pix = page.get_pixmap(alpha=False)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                text = pytesseract.image_to_string(img)
                if text and text.strip():
                    docs.append({
                        "page_content": text.strip(),
                        "metadata": {"type": "ocr", "source": os.path.basename(pdf_path), "page": i+1}
                    })
            doc.close()
        except Exception:
            return []
        return docs
    def extract_from_pdf_simple(self, pdf_path: str) -> str:
        try:
            import fitz
            doc = fitz.open(pdf_path)
            text = ""
            for page in doc:
                text += page.get_text() + "\n"
            doc.close()
            return text.strip()
        except Exception:
            return ""
