from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum as EnumType
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Enum, JSON, Boolean
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func

from ..core.database import Base

class DocumentStatus(str, EnumType):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    ERROR = "error"

class DocumentType(str, EnumType):
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    MARKDOWN = "markdown"
    HTML = "html"
    UNKNOWN = "unknown"

class Document(Base):
    __tablename__ = "documents"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)  # in bytes
    file_type: Mapped[DocumentType] = mapped_column(Enum(DocumentType), default=DocumentType.UNKNOWN)
    mime_type: Mapped[str] = mapped_column(String(100))
    
    # Metadata
    metadata_: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, default={})
    status: Mapped[DocumentStatus] = mapped_column(Enum(DocumentStatus), default=DocumentStatus.UPLOADED)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Timestamps
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Relationships
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    owner: Mapped["User"] = relationship("User", back_populates="documents")
    
    chunks: Mapped[List["DocumentChunk"]] = relationship(
        "DocumentChunk", 
        back_populates="document",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Document {self.title} ({self.file_type})>"
    
    @property
    def is_processed(self) -> bool:
        return self.status == DocumentStatus.PROCESSED

class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, default={})
    
    # Vector embedding
    embedding_id: Mapped[Optional[str]] = mapped_column(String(255))  # Reference to vector DB
    
    # Relationships
    document_id: Mapped[int] = mapped_column(Integer, ForeignKey("documents.id", ondelete="CASCADE"))
    document: Mapped[Document] = relationship("Document", back_populates="chunks")
    
    def __repr__(self) -> str:
        return f"<DocumentChunk {self.chunk_index} of document {self.document_id}>"
