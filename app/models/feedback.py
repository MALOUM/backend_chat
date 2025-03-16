from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

class FeedbackRating(str, Enum):
    """Notation possible pour les feedbacks"""
    VERY_POOR = "very_poor"
    POOR = "poor"
    NEUTRAL = "neutral"
    GOOD = "good"
    VERY_GOOD = "very_good"

class FeedbackCategory(str, Enum):
    """Catégories de feedback possibles"""
    RELEVANCE = "relevance"      # Pertinence des informations
    ACCURACY = "accuracy"        # Précision factuelle
    COMPLETENESS = "completeness" # Complétude de la réponse
    CLARITY = "clarity"          # Clarté de la réponse
    GENERAL = "general"          # Feedback général

class Feedback(BaseModel):
    """Modèle de feedback utilisateur sur les réponses du système"""
    _id: str
    user_id: str
    message_id: str
    session_id: str
    rating: FeedbackRating
    category: FeedbackCategory = FeedbackCategory.GENERAL
    comment: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        allow_population_by_field_name = True
        schema_extra = {
            "example": {
                "_id": "abc123",
                "user_id": "user456",
                "message_id": "msg789",
                "session_id": "session123",
                "rating": "good",
                "category": "relevance",
                "comment": "La réponse était pertinente mais aurait pu inclure plus de détails.",
                "timestamp": "2023-08-15T14:30:00",
                "metadata": {"rag_used": True, "source_count": 3}
            }
        } 