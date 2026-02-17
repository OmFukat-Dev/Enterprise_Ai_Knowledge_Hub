import streamlit as st
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer, CrossEncoder
import yaml

st.title("Enterprise RAG Evaluation Dashboard")

with open("../config/config.yaml") as f:
    config = yaml.safe_load(f)

client = QdrantClient(path="../data/qdrant_db")
model = SentenceTransformer(config["embedding_model"])
reranker = CrossEncoder(config["reranker_model"])

query = st.text_input("Test Query")
if st.button("Evaluate"):
    hits = client.search(
        collection_name=config["collection_name"],
        query_vector=model.encode(query).tolist(),
        limit=10
    )
    for i, hit in enumerate(hits):
        st.write(f"**Rank {i+1}** | Score: {hit.score:.4f}")
        st.write(hit.payload["text"][:500] + "...")
        st.divider()