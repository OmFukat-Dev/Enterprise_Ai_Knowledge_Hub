from transformers import AutoModelForSequenceClassification, AutoTokenizer
import torch

class CrossEncoderReranker:
    def __init__(self, model_name="BAAI/bge-reranker-large"):
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
        self.model.eval()

    def rerank(self, query: str, documents: list[str], top_k=5):
        pairs = [[query, doc] for doc in documents]
        with torch.no_grad():
            inputs = self.tokenizer(pairs, padding=True, truncation=True, return_tensors='pt', max_length=512)
            scores = self.model(**inputs).logits.squeeze(-1).cpu().numpy()
        sorted_results = sorted(zip(documents, scores), key=lambda x: x[1], reverse=True)[:top_k]
        return [doc for doc, score in sorted_results]