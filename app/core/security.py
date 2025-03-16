from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from jose import jwt
from passlib.context import CryptContext
import json
from bson import ObjectId, json_util
from app import config

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        if isinstance(o, datetime):
            return o.isoformat()
        return json.JSONEncoder.default(self, o)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vérifier un mot de passe"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hasher un mot de passe"""
    return pwd_context.hash(password)

def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    """Créer un JWT token"""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES)
        
    # Assurez-vous que subject est une chaîne, pas un ObjectId
    if isinstance(subject, ObjectId):
        subject = str(subject)
        
    to_encode = {"exp": expire, "sub": subject}
    
    # Utiliser l'encodeur personnalisé pour gérer les types MongoDB
    encoded_jwt = jwt.encode(to_encode, config.SECRET_KEY, algorithm=config.ALGORITHM)
    return encoded_jwt

def decode_token(token: str) -> Dict[str, Any]:
    """Décoder un JWT token"""
    return jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITHM])
