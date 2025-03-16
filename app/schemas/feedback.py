from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from app.models.feedback import FeedbackRating, FeedbackCategory

class FeedbackCreate(BaseModel):
    """Schéma pour la création d'un feedback"""
    message_id: str
    rating: FeedbackRating
    category: FeedbackCategory = FeedbackCategory.GENERAL
    comment: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class FeedbackUpdate(BaseModel):
    """Schéma pour la mise à jour d'un feedback"""
    rating: Optional[FeedbackRating] = None
    category: Optional[FeedbackCategory] = None
    comment: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class FeedbackResponse(BaseModel):
    """Schéma pour la réponse de feedback"""
    id: str
    user_id: str
    message_id: str
    session_id: str
    rating: FeedbackRating
    category: FeedbackCategory
    comment: Optional[str]
    timestamp: datetime
    metadata: Dict[str, Any]

class FeedbackStats(BaseModel):
    """Statistiques des feedbacks"""
    total_count: int
    average_rating: float
    ratings_distribution: Dict[str, int]
    category_distribution: Dict[str, int] 