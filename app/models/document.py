from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

class DocumentType(str, Enum):
    """Types de documents"""
    TEXT = "text"
    PDF = "pdf"
    URL = "url"
    IMAGE = "image"

class ProcessingStatus(str, Enum):
    """Statuts de traitement des documents"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class DocumentMetadata(BaseModel):
    """Métadonnées des documents"""
    source: Optional[str] = None
    author: Optional[str] = None
    created_date: Optional[datetime] = None
    tags: List[str] = Field(default_factory=list)
    properties: Dict[str, Any] = Field(default_factory=dict)

class Document(BaseModel):
    """Modèle de document"""
    _id: str
    user_id: str
    title: str
    type: DocumentType
    content: str
    url: Optional[str] = None
    status: ProcessingStatus = ProcessingStatus.PENDING
    metadata: DocumentMetadata = Field(default_factory=DocumentMetadata)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class DocumentChunk(BaseModel):
    """Modèle de chunk de document"""
    _id: str
    document_id: str
    chunk_index: int
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    embedding_id: Optional[str] = None
