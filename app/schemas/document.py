from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, HttpUrl
from datetime import datetime
from enum import Enum
from app.models.document import DocumentType, ProcessingStatus, DocumentMetadata

class DocumentCreate(BaseModel):
    """Schéma pour la création de document"""
    title: str
    type: DocumentType
    content: Optional[str] = None
    url: Optional[HttpUrl] = None
    metadata: Optional[Dict[str, Any]] = None

class DocumentUpdate(BaseModel):
    """Schéma pour la mise à jour de document"""
    title: Optional[str] = None
    content: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class DocumentResponse(BaseModel):
    """Schéma pour la réponse de document"""
    id: str
    user_id: str
    title: str
    type: DocumentType
    url: Optional[str] = None
    status: ProcessingStatus
    metadata: DocumentMetadata
    created_at: datetime
    updated_at: datetime

class DocumentChunkResponse(BaseModel):
    """Schéma pour la réponse de chunk de document"""
    id: str
    document_id: str
    chunk_index: int
    content: str
    metadata: Dict[str, Any]

class ChunkingStrategy(str, Enum):
    """Stratégies de chunking disponibles"""
    FIXED_SIZE = "fixed_size"
    RECURSIVE = "recursive"
    SEMANTIC = "semantic"
    SENTENCE = "sentence"
    PARAGRAPH = "paragraph"