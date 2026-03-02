
import os
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent
sys.path.insert(0, str(_root))

from src.ingestion.extract_text import TextExtractor
from src.ingestion.chunking import semantic_chunk_documents

def debug_extraction(pdf_path):
    print(f"Testing extraction for: {pdf_path}")
    extractor = TextExtractor()
    
    # Try advanced extraction
    docs = extractor.extract_from_pdf_advanced(pdf_path)
    print(f"Extracted {len(docs)} pages.")
    
    if not docs:
        print("❌ No text extracted!")
        return
    
    for i, doc in enumerate(docs):
        print(f"--- Page {i+1} content snippet ---")
        print(doc["page_content"][:500])
        print("-" * 40)
        
    # Try chunking
    chunks = semantic_chunk_documents(docs)
    print(f"Produced {len(chunks)} chunks.")
    if chunks:
        print(f"First chunk snippet: {chunks[0]['page_content'][:200]}")

if __name__ == "__main__":
    import glob
    pdfs = glob.glob("tmp/*.pdf")
    if not pdfs:
        print("No PDFs found in tmp/ to test.")
    else:
        debug_extraction(pdfs[0])
