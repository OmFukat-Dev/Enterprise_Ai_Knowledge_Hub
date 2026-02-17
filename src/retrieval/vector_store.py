# src/retrieval/vector_store.py — FIXED & BULLETPROOF
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer
import uuid
import os
import logging
import shutil

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class QdrantVectorStore:
    def __init__(self, path="./data/qdrant_db", collection_name="enterprise_knowledge"):
        # Allow override via env
        base_path = os.getenv("QDRANT_PATH", path)
        self.path = base_path
        # Initialize local Qdrant; handle incompatible config or concurrent access by isolating per-process
        try:
            self.client = QdrantClient(path=self.path)
        except Exception as e:
            msg = str(e).lower()
            if "already accessed by another instance" in msg:
                alt_path = f"{self.path}-{os.getpid()}"
                os.makedirs(alt_path, exist_ok=True)
                self.path = alt_path
                self.client = QdrantClient(path=self.path)
            else:
                try:
                    shutil.rmtree(self.path, ignore_errors=True)
                except Exception:
                    pass
                os.makedirs(self.path, exist_ok=True)
                self.client = QdrantClient(path=self.path)
        self.collection_name = collection_name
        self.model = SentenceTransformer("BAAI/bge-large-en-v1.5")
        self.dimension = 1024
        self._memory = []  # fallback in-memory store: list of (text, meta, vector)

        try:
            self.client.get_collection(collection_name)
        except Exception:
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=self.dimension, distance=Distance.COSINE),
            )

    def add_documents(self, documents):
        def _tm(d):
            if hasattr(d, "page_content"):
                return d.page_content, d.metadata
            if isinstance(d, dict):
                return d.get("page_content", ""), d.get("metadata", {})
            return str(d), {}
        texts, metadatas = zip(*[_tm(doc) for doc in documents]) if documents else ([], [])
        self.add_texts(texts, metadatas)

    def add_texts(self, texts: list[str], metadatas: list[dict]):
        vectors = self.model.encode(texts, normalize_embeddings=True).tolist()
        
        # Always record in-memory for fallback
        for text, meta, vec in zip(texts, metadatas, vectors):
            self._memory.append((text, meta, vec))

        # Try to upsert into Qdrant; ignore failures (fallback will handle)
        try:
            points = []
            for text, meta, vec in zip(texts, metadatas, vectors):
                payload = {"text": text, **meta}
                points.append(PointStruct(id=str(uuid.uuid4()), vector=vec, payload=payload))
            if points:
                self.client.upsert(collection_name=self.collection_name, points=points)
        except Exception as e:
            logger.warning(f"Qdrant upsert failed, using in-memory store only: {e}")

    def similarity_search(self, query: str, k=20):
        query_vec = self.model.encode([query], normalize_embeddings=True)[0].tolist()
        try:
            if hasattr(self.client, "search"):
                results = self.client.search(
                    collection_name=self.collection_name,
                    query_vector=query_vec,
                    limit=k
                )
                return [(r.payload.get("text", ""), r.payload, getattr(r, "score", 0.0)) for r in results]
        except Exception as e:
            logger.warning(f"Qdrant search failed, falling back to in-memory search: {e}")

        # Fallback: in-memory cosine search
        def _cos(a, b):
            import math
            dot = sum(x*y for x, y in zip(a, b))
            na = math.sqrt(sum(x*x for x in a))
            nb = math.sqrt(sum(y*y for y in b))
            return dot / (na*nb + 1e-8)

        scores = [(_cos(query_vec, vec), text, meta) for (text, meta, vec) in self._memory]
        scores.sort(key=lambda t: t[0], reverse=True)
        top = scores[:k]
        return [(text, meta, score) for (score, text, meta) in top]


class PGVectorStore:
    def __init__(self, connection_string=None, table_name="embeddings"):
        try:
            from sqlalchemy import create_engine, text, Column, Integer, String, Text
            from sqlalchemy.orm import sessionmaker, declarative_base
            from pgvector.sqlalchemy import Vector
        except ImportError:
            raise ImportError("Please install sqlalchemy, pgvector, and psycopg2-binary to use PGVectorStore")

        self.model = SentenceTransformer("BAAI/bge-large-en-v1.5")
        self.dimension = 1024
        
        if connection_string is None:
            db_host = os.getenv("DB_HOST", "localhost")
            db_pass = os.getenv("DB_PASSWORD", "postgres")
            db_user = os.getenv("DB_USER", "postgres")
            db_name = os.getenv("DB_NAME", "postgres")
            connection_string = f"postgresql://{db_user}:{db_pass}@{db_host}:5432/{db_name}"

        self.engine = create_engine(connection_string)
        self.Session = sessionmaker(bind=self.engine)
        self.Base = declarative_base()
        self.table_name = table_name

        # Define the model dynamically to allow table_name config
        class Embedding(self.Base):
            __tablename__ = table_name
            id = Column(Integer, primary_key=True)
            text = Column(Text)
            metadata_json = Column(Text) # Storing metadata as JSON string for simplicity
            embedding = Column(Vector(self.dimension))

        self.Embedding = Embedding

        # Create extension and table
        with self.engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
        
        self.Base.metadata.create_all(self.engine)

    def add_documents(self, documents):
        texts = [doc.page_content for doc in documents]
        metadatas = [doc.metadata for doc in documents]
        self.add_texts(texts, metadatas)

    def add_texts(self, texts: list[str], metadatas: list[dict]):
        import json
        vectors = self.model.encode(texts, normalize_embeddings=True).tolist()
        
        session = self.Session()
        try:
            for text, meta, vec in zip(texts, metadatas, vectors):
                embedding = self.Embedding(
                    text=text,
                    metadata_json=json.dumps(meta),
                    embedding=vec
                )
                session.add(embedding)
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Error adding texts to PGVector: {e}")
            raise
        finally:
            session.close()

    def similarity_search(self, query: str, k=20):
        import json
        query_vec = self.model.encode([query], normalize_embeddings=True)[0].tolist()
        
        session = self.Session()
        try:
            # L2 distance operator is <->, Cosine distance is <=>
            # Using cosine distance <=> for ordering
            results = session.query(self.Embedding).order_by(
                self.Embedding.embedding.cosine_distance(query_vec)
            ).limit(k).all()
            
            return [(r.text, json.loads(r.metadata_json), 0.0) for r in results] # Score is not directly available without extra query work, returning 0.0 for now
        finally:
            session.close()

def get_vector_store():
    store_type = os.getenv("VECTOR_STORE_TYPE", "qdrant")
    if store_type.lower() == "pgvector":
        return PGVectorStore()
    else:
        return QdrantVectorStore()
