from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta
from typing import Any
import uuid
from bson.objectid import ObjectId
from bson.json_util import loads, dumps
import json
import logging

from app.schemas.auth import TokenSchema, UserLogin, UserRegistration
from app.models.user import UserCreate, UserInDB
from app.core.security import verify_password, get_password_hash, create_access_token
from app.db.mongodb import get_user_collection
from app.dependencies import get_current_active_user
from app import config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=TokenSchema)
async def register_user(user_data: UserRegistration) -> Any:
    """
    Enregistrer un nouvel utilisateur et renvoyer un token d'accès.
    """
    user_collection = await get_user_collection()
    
    # Vérifier si l'email existe déjà
    existing_email = await user_collection.find_one({"email": user_data.email})
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email déjà enregistré",
        )
    
    # Vérifier si le nom d'utilisateur existe déjà
    existing_username = await user_collection.find_one({"username": user_data.username})
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nom d'utilisateur déjà pris",
        )
    
    # Hasher le mot de passe
    hashed_password = get_password_hash(user_data.password)
    
    # Créer l'utilisateur
    new_user = UserCreate(
        email=user_data.email,
        username=user_data.username,
        password=hashed_password
    )
    
    # Créer un ObjectId pour l'utilisateur
    user_id = ObjectId()
    
    user_in_db = UserInDB(
        _id=str(user_id),  # Utiliser un ID compatible avec Pydantic
        email=new_user.email,
        username=new_user.username,
        is_active=True,
        hashed_password=hashed_password
    )
    
    # Insérer l'utilisateur avec l'ObjectId explicite
    user_doc = user_in_db.dict(by_alias=True)
    user_doc["_id"] = user_id  # Remplacer l'ID string par l'ObjectId
    
    await user_collection.insert_one(user_doc)
    
    logger.info(f"Utilisateur créé avec ID: {str(user_id)}")
    
    # Créer le token d'accès
    access_token = create_access_token(
        subject=str(user_id),
        expires_delta=timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

@router.post("/token", response_model=TokenSchema)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()) -> Any:
    """
    OAuth2 compatible token login, renvoie un token d'accès.
    """
    user_collection = await get_user_collection()
    user = await user_collection.find_one({"email": form_data.username})
    
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Utiliser l'ID sous forme de chaîne pour le token
    user_id = str(user["_id"])
    
    logger.info(f"Connexion réussie pour l'utilisateur avec ID: {user_id}")
    
    access_token = create_access_token(
        subject=user_id,
        expires_delta=timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

@router.post("/login", response_model=TokenSchema)
async def login(user_data: UserLogin) -> Any:
    """
    Login utilisateur, renvoie un token d'accès.
    """
    user_collection = await get_user_collection()
    user = await user_collection.find_one({"email": user_data.email})
    
    if not user or not verify_password(user_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Utiliser l'ID sous forme de chaîne pour le token
    user_id = str(user["_id"])
    
    logger.info(f"Connexion réussie pour l'utilisateur avec ID: {user_id}")
    
    access_token = create_access_token(
        subject=user_id,
        expires_delta=timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

@router.post("/logout")
async def logout(
    current_user: UserInDB = Depends(get_current_active_user)
) -> Any:
    """
    Déconnexion de l'utilisateur.
    Le frontend doit supprimer le token manuellement.
    Cette fonction permet d'ajouter le token à une liste de révocation (blacklist).
    """
    try:
        # Dans une implémentation complète, on ajouterait ici le token à une liste de révocation
        # Exemple avec Redis : await redis.setex(f"blacklist:{token}", expiration_time, "true")
        
        logger.info(f"Déconnexion réussie pour l'utilisateur avec ID: {current_user.id}")
        
        return {
            "message": "Déconnexion réussie"
        }
    except Exception as e:
        logger.error(f"Erreur lors de la déconnexion: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la déconnexion"
        )