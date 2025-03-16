from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
from app.models.chat import MessageRole

class MessageCreate(BaseModel):
    """Schéma pour la création de message"""
    content: str
    role: MessageRole = MessageRole.USER
    metadata: Dict[str, Any] = Field(default_factory=dict)

class MessageResponse(BaseModel):
    """Schéma pour la réponse de message"""
    id: str
    session_id: str
    role: MessageRole
    content: str
    metadata: Dict[str, Any]
    timestamp: datetime

class ChatSessionCreate(BaseModel):
    """Schéma pour la création de session de chat"""
    title: str
    rag_enabled: bool = True
    rag_strategy: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ChatSessionUpdate(BaseModel):
    """Schéma pour la mise à jour de session de chat"""
    title: Optional[str] = None
    rag_enabled: Optional[bool] = None
    rag_strategy: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class ChatSessionResponse(BaseModel):
    """Schéma pour la réponse de session de chat"""
    id: str
    user_id: str
    title: str
    rag_enabled: bool
    rag_strategy: Optional[str]
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any]

class StreamingRequest(BaseModel):
    """Schéma pour la requête de streaming"""
    session_id: str
    message: str
    rag_enabled: bool = True
    rag_strategy: Optional[str] = None

class CancelResponse(BaseModel):
    """Schéma pour la réponse d'annulation de streaming"""
    status: str  # "success" ou "not_found"
    message: str

class RAGStrategyEnum(str, Enum):
    """Stratégies RAG disponibles"""
    BASIC = "basic"
    SEMANTIC_CHUNKING = "semantic_chunking"
    HYBRID_SEARCH = "hybrid_search"
    RERANKING = "reranking"
    RECURSIVE = "recursive"