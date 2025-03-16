from typing import Optional
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime
from bson import ObjectId

class UserBase(BaseModel):
    """Modèle de base pour les utilisateurs"""
    email: EmailStr
    username: str
    is_active: bool = True

class UserCreate(UserBase):
    """Modèle pour la création d'utilisateur"""
    password: str

class UserUpdate(BaseModel):
    """Modèle pour la mise à jour d'utilisateur"""
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None

class UserInDB(UserBase):
    """Modèle pour l'utilisateur en base de données"""
    id: str  # L'ID est stocké sous forme de chaîne dans le modèle Pydantic
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        # Configuration pour Pydantic v1
        allow_population_by_field_name = True
        
        # Configuration pour Pydantic v2
        populate_by_name = True
        
        # Mapper les noms de champs entre MongoDB et Pydantic
        field_map = {'id': '_id'}
        alias_generator = lambda field: "_id" if field == "id" else field
        
        # Personnalisation du schéma JSON
        json_schema_extra = {
            "example": {
                "id": "507f1f77bcf86cd799439011",
                "email": "user@example.com",
                "username": "johndoe",
                "is_active": True,
                "hashed_password": "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW"
            }
        }

class User(UserBase):
    """Modèle d'utilisateur pour les réponses API"""
    id: str
    created_at: datetime