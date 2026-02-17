def semantic_chunk_documents(documents: list, chunk_size=1024, chunk_overlap=200):
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", "! ", "? ", " ", ""]
        )
        return text_splitter.split_documents(documents)
    except Exception:
        chunks = []
        for d in documents:
            if hasattr(d, "page_content"):
                text = d.page_content
                meta = getattr(d, "metadata", {})
            elif isinstance(d, dict):
                text = d.get("page_content", "")
                meta = d.get("metadata", {})
            else:
                text = str(d)
                meta = {}
            start = 0
            while start < len(text):
                end = min(len(text), start + chunk_size)
                chunk_text = text[start:end]
                chunks.append({"page_content": chunk_text, "metadata": meta})
                if end >= len(text):
                    break
                start = max(0, end - chunk_overlap)
        return chunks
