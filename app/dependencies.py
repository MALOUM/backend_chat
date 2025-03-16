from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from datetime import datetime, timedelta
from bson.objectid import ObjectId
from bson.errors import InvalidId
import logging

from app.core.security import decode_token
from app.db.mongodb import get_user_collection
from app.models.user import UserInDB
from app import config

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{config.API_PREFIX}/auth/token")

async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserInDB:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Impossible de valider les informations d'identification",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        logger.info(f"Tentative de décodage du token: {token[:20]}...")
        payload = decode_token(token)
        user_id: str = payload.get("sub")
        logger.info(f"ID utilisateur extrait du token: {user_id}")
        
        if user_id is None:
            logger.error("ID utilisateur non trouvé dans le token")
            raise credentials_exception
    except JWTError as e:
        logger.error(f"Erreur de décodage JWT: {str(e)}")
        raise credentials_exception
    
    user_collection = await get_user_collection()
    
    # Tenter de convertir l'ID en ObjectId pour la recherche
    try:
        if ObjectId.is_valid(user_id):
            object_id = ObjectId(user_id)
            logger.info(f"Recherche de l'utilisateur avec ObjectId: {object_id}")
            user_data = await user_collection.find_one({"_id": object_id})
        else:
            # Recherche par ID de chaîne en dernier recours
            logger.info(f"Recherche de l'utilisateur avec ID chaîne: {user_id}")
            user_data = await user_collection.find_one({"_id": user_id})
    except InvalidId as e:
        logger.error(f"ID utilisateur invalide: {str(e)}")
        raise credentials_exception
    
    if user_data is None:
        logger.error(f"Aucun utilisateur trouvé avec l'ID: {user_id}")
        raise credentials_exception
    
    # Convertir ObjectId en chaîne pour le modèle Pydantic
    if isinstance(user_data["_id"], ObjectId):
        user_data["_id"] = str(user_data["_id"])
    
    logger.info(f"Utilisateur trouvé: {user_data.get('username')}")
    return UserInDB(**user_data)

async def get_current_active_user(current_user: UserInDB = Depends(get_current_user)) -> UserInDB:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Utilisateur inactif")
    return current_user