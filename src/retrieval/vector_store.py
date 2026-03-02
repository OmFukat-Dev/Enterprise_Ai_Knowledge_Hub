# src/retrieval/vector_store.py - PRODUCTION-READY RAG VECTOR STORE
import uuid
import os
import logging
import shutil
from typing import List, Tuple, Dict, Any, Optional

logger = logging.getLogger(__name__)


class QdrantVectorStore:
    """
    Local on-disk Qdrant vector store using BAAI/bge-large-en-v1.5 embeddings.

    Fixes applied:
    - Bug 2: uuid.uuid4() directly (not the redundant double-wrap)
    - Bug 3: get_document_count() uses client.count() — points_count is deprecated
    - Bug 4: _memory is a true fallback; only populated when Qdrant fails
    """

    def __init__(
        self,
        path: str = "./data/qdrant_db",
        collection_name: str = "enterprise_knowledge",
    ):
        base_path = os.getenv("QDRANT_PATH", path)
        self.path = base_path
        self.collection_name = os.getenv("QDRANT_COLLECTION", collection_name)
        self.score_threshold = float(os.getenv("SCORE_THRESHOLD", "0.0"))
        self._memory: List[Tuple[str, dict, list]] = []  # (text, meta, vector) — fallback only

        # ── Initialise Qdrant client ──────────────────────────────────────────
        self.client = self._init_client()

        # ── Load embedding model (cached singleton) ───────────────────────────
        from src.retrieval.models import get_embedding_model
        self.model = get_embedding_model()
        self.dimension = self.model.get_sentence_embedding_dimension()
        logger.info(f"Using embedding model singleton (dim={self.dimension})")

        # ── Ensure collection exists ──────────────────────────────────────────
        self._ensure_collection()

    def _init_client(self):
        """Initialise QdrantClient with robust fallback on lock conflicts."""
        from qdrant_client import QdrantClient
        import random

        os.makedirs(self.path, exist_ok=True)
        try:
            client = QdrantClient(path=self.path)
            return client
        except (Exception, RuntimeError) as e:
            msg = str(e).lower()
            if "already accessed by another instance" in msg:
                # Use a unique path per-process to avoid lock conflicts
                alt = f"{self.path}-{os.getpid()}-{random.randint(1000, 9999)}"
                os.makedirs(alt, exist_ok=True)
                logger.warning(f"Qdrant lock conflict on '{self.path}'. Using isolated path: {alt}")
                self.path = alt
                try:
                    return QdrantClient(path=self.path)
                except Exception as inner_e:
                    logger.error(f"Failed to open isolated Qdrant: {inner_e}. Using in-memory only.")
                    return QdrantClient(":memory:")
            else:
                # Corrupted DB or other error — wipe and recreate
                logger.warning("Qdrant init error; recreating DB. Error: %s", e)
                try:
                    shutil.rmtree(self.path, ignore_errors=True)
                    os.makedirs(self.path, exist_ok=True)
                    return QdrantClient(path=self.path)
                except Exception:
                    return QdrantClient(":memory:")

    def _ensure_collection(self):
        from qdrant_client.http.models import Distance, VectorParams

        try:
            info = self.client.get_collection(self.collection_name)
            existing_dim = info.config.params.vectors.size
            if existing_dim != self.dimension:
                logger.warning(
                    f"Collection dimension mismatch ({existing_dim} vs {self.dimension}). "
                    "Recreating collection."
                )
                self.client.delete_collection(self.collection_name)
                raise Exception("dimension mismatch — recreate")
        except Exception:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.dimension, distance=Distance.COSINE
                ),
            )
            logger.info(f"Created Qdrant collection '{self.collection_name}' (dim={self.dimension})")

    def _qdrant_search(self, query_vec: list, k: int, score_threshold: float):
        """
        Compatibility layer for qdrant-client versions:
        - Older versions expose `search(...)`
        - Newer versions expose `query_points(...)`
        """
        if hasattr(self.client, "search"):
            return self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vec,
                limit=k,
                score_threshold=score_threshold if score_threshold > 0.0 else None,
            )

        if hasattr(self.client, "query_points"):
            result = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vec,
                limit=k,
                score_threshold=score_threshold if score_threshold > 0.0 else None,
            )
            points = getattr(result, "points", None)
            if points is not None:
                return points
            if isinstance(result, tuple) and result:
                return result[0]
            return result

        raise AttributeError("Qdrant client has neither 'search' nor 'query_points'")

    # ── Public API ────────────────────────────────────────────────────────────

    def add_documents(self, documents: list):
        """Accept dicts or LangChain Document objects."""
        def _extract(d):
            if hasattr(d, "page_content"):
                return d.page_content, d.metadata
            if isinstance(d, dict):
                return d.get("page_content", ""), d.get("metadata", {})
            return str(d), {}

        pairs = [_extract(doc) for doc in documents]
        texts = [p[0] for p in pairs]
        metas = [p[1] for p in pairs]
        # Filter empty texts
        filtered = [(t, m) for t, m in zip(texts, metas) if t and t.strip()]
        if not filtered:
            return
        self.add_texts([t for t, m in filtered], [m for t, m in filtered])

    def add_texts(self, texts: List[str], metadatas: List[Dict[str, Any]]):
        """Encode texts and upsert into Qdrant. Falls back to in-memory only on failure."""
        from qdrant_client.http.models import PointStruct

        vectors = self.model.encode(
            texts, normalize_embeddings=True, show_progress_bar=False
        ).tolist()

        # Bug 2 Fix: uuid.uuid4() returns a uuid.UUID directly — no double-wrap needed
        points = []
        for text, meta, vec in zip(texts, metadatas, vectors):
            payload = {"text": text, **{
                k: (str(v) if not isinstance(v, (str, int, float, bool)) else v)
                for k, v in meta.items()
            }}
            points.append(
                PointStruct(
                    id=uuid.uuid4(),   # ← Direct uuid.UUID, no redundant str() wrapping
                    vector=vec,
                    payload=payload,
                )
            )

        # Bug 4 Fix: Only append to _memory when Qdrant fails (true fallback, not always)
        try:
            if points:
                self.client.upsert(
                    collection_name=self.collection_name, points=points
                )
                logger.info(f"Upserted {len(points)} points into Qdrant.")
                # Qdrant succeeded — do NOT populate _memory (prevents RAM leak)
        except Exception as e:
            logger.warning(f"Qdrant upsert failed — using in-memory fallback: {e}")
            # Only on failure do we populate the in-memory store
            for text, meta, vec in zip(texts, metadatas, vectors):
                self._memory.append((text, meta, vec))

    def similarity_search(
        self,
        query: str,
        k: int = 20,
        score_threshold: float = 0.0,
    ) -> List[Tuple[str, dict, float]]:
        """
        Return top-k (text, metadata, score) tuples for a query.
        Falls back to in-memory cosine search if Qdrant fails.
        """
        query_vec = self.model.encode(
            [query], normalize_embeddings=True
        )[0].tolist()

        effective_threshold = score_threshold if score_threshold > 0.0 else self.score_threshold

        # ── Qdrant search ─────────────────────────────────────────────────────
        try:
            results = self._qdrant_search(query_vec, k, effective_threshold)
            if results:
                return [
                    (
                        r.payload.get("text", ""),
                        {k: v for k, v in r.payload.items() if k != "text"},
                        getattr(r, "score", 0.0),
                    )
                    for r in results
                ]
        except Exception as e:
            logger.warning(f"Qdrant search failed, falling back to in-memory: {e}")

        # ── In-memory cosine search fallback ─────────────────────────────────
        return self._memory_search(query_vec, k, effective_threshold)

    def get_document_count(self) -> int:
        """Return number of indexed vectors (for diagnostics)."""
        # Bug 3 Fix: points_count is deprecated in qdrant-client >= 1.7
        # Use client.count() which is stable across versions
        try:
            result = self.client.count(
                collection_name=self.collection_name,
                exact=True,
            )
            return result.count or 0
        except Exception:
            # Fallback to in-memory count (only populated if Qdrant failed)
            return len(self._memory)

    def clear(self):
        """Remove all documents from the store (use with caution)."""
        try:
            self.client.delete_collection(self.collection_name)
            self._ensure_collection()
        except Exception:
            pass
        self._memory.clear()
        logger.info("Vector store cleared.")

    # ── Private helpers ───────────────────────────────────────────────────────

    def _memory_search(
        self,
        query_vec: list,
        k: int,
        score_threshold: float,
    ) -> List[Tuple[str, dict, float]]:
        import math

        def _cos(a, b):
            dot = sum(x * y for x, y in zip(a, b))
            na = math.sqrt(sum(x * x for x in a))
            nb = math.sqrt(sum(y * y for y in b))
            return dot / (na * nb + 1e-8)

        scored = [
            (_cos(query_vec, vec), text, meta)
            for text, meta, vec in self._memory
        ]
        scored.sort(key=lambda t: t[0], reverse=True)
        top = scored[:k]
        if score_threshold > 0.0:
            top = [item for item in top if item[0] >= score_threshold]
        return [(text, meta, score) for score, text, meta in top]


# ── PGVector store (unchanged, kept for compatibility) ────────────────────────
class PGVectorStore:
    def __init__(self, connection_string: Optional[str] = None, table_name: str = "embeddings"):
        try:
            from sqlalchemy import create_engine, Column, Integer, String, Text
            from sqlalchemy.orm import sessionmaker, declarative_base
            from pgvector.sqlalchemy import Vector
        except ImportError:
            raise ImportError(
                "Install sqlalchemy, pgvector, and psycopg2-binary for PGVectorStore"
            )
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(
            os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")
        )
        self.dimension = self.model.get_sentence_embedding_dimension()

        if connection_string is None:
            db_host = os.getenv("DB_HOST", "localhost")
            db_pass = os.getenv("DB_PASSWORD", "postgres")
            db_user = os.getenv("DB_USER", "postgres")
            db_name = os.getenv("DB_NAME", "postgres")
            connection_string = (
                f"postgresql://{db_user}:{db_pass}@{db_host}:5432/{db_name}"
            )

        self.engine = create_engine(connection_string)
        Session = sessionmaker(bind=self.engine)
        self.Session = Session
        Base = declarative_base()
        self.table_name = table_name

        dim = self.dimension

        class Embedding(Base):
            __tablename__ = table_name
            id = Column(Integer, primary_key=True)
            text = Column(Text)
            metadata_json = Column(Text)
            embedding = Column(Vector(dim))

        self.Embedding = Embedding

        with self.engine.connect() as conn:
            from sqlalchemy import text
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
        Base.metadata.create_all(self.engine)

    def add_documents(self, documents):
        texts = [doc.page_content for doc in documents]
        metadatas = [doc.metadata for doc in documents]
        self.add_texts(texts, metadatas)

    def add_texts(self, texts: List[str], metadatas: List[dict]):
        import json
        vectors = self.model.encode(texts, normalize_embeddings=True).tolist()
        session = self.Session()
        try:
            for text, meta, vec in zip(texts, metadatas, vectors):
                session.add(
                    self.Embedding(
                        text=text,
                        metadata_json=json.dumps(meta),
                        embedding=vec,
                    )
                )
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"PGVector upsert error: {e}")
            raise
        finally:
            session.close()

    def similarity_search(
        self, query: str, k: int = 20, score_threshold: float = 0.0
    ) -> List[Tuple[str, dict, float]]:
        import json
        query_vec = self.model.encode([query], normalize_embeddings=True)[0].tolist()
        session = self.Session()
        try:
            rows = (
                session.query(self.Embedding)
                .order_by(self.Embedding.embedding.cosine_distance(query_vec))
                .limit(k)
                .all()
            )
            return [(r.text, json.loads(r.metadata_json), 0.0) for r in rows]
        finally:
            session.close()

    def get_document_count(self) -> int:
        session = self.Session()
        try:
            return session.query(self.Embedding).count()
        finally:
            session.close()


# ── Factory ───────────────────────────────────────────────────────────────────
def get_vector_store():
    store_type = os.getenv("VECTOR_STORE_TYPE", "qdrant").lower()
    if store_type == "pgvector":
        return PGVectorStore()
    return QdrantVectorStore()
