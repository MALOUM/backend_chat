from typing import Optional
from pydantic import BaseModel, EmailStr

class TokenSchema(BaseModel):
    """Schéma de token d'accès"""
    access_token: str
    token_type: str

class TokenPayload(BaseModel):
    """Contenu du payload JWT"""
    sub: Optional[str] = None
    
class UserLogin(BaseModel):
    """Schéma pour la connexion utilisateur"""
    email: EmailStr
    password: str

class UserRegistration(BaseModel):
    """Schéma pour l'inscription utilisateur"""
    username: str
    email: EmailStr
    password: str