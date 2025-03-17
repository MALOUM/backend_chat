from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks, Query
from typing import List, Optional, Any
from datetime import datetime
import uuid
from sse_starlette.sse import EventSourceResponse
import asyncio
import json
import logging
from bson import ObjectId

from app.dependencies import get_current_active_user
from app.models.user import UserInDB
from app.models.chat import ChatSession, ChatMessage, MessageRole
from app.schemas.chat import (
    ChatSessionCreate, ChatSessionUpdate, ChatSessionResponse,
    MessageCreate, MessageResponse, StreamingRequest, RAGStrategyEnum,
    CancelResponse
)
from app.db.mongodb import get_chat_session_collection, get_message_collection
from app.core.chat_processor import ChatProcessor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])

# Sessions de chat
@router.post("/sessions", response_model=ChatSessionResponse)
async def create_chat_session(
    session: ChatSessionCreate,
    current_user: UserInDB = Depends(get_current_active_user)
) -> Any:
    """
    Créer une nouvelle session de chat.
    """
    logger.info(f"Création d'une session de chat pour l'utilisateur {current_user.id}")
    
    session_collection = await get_chat_session_collection()
    
    # Créer une nouvelle session
    now = datetime.utcnow()
    
    # Créer un dictionnaire de session sans spécifier l'ID
    session_dict = {
        "title": session.title,
        "user_id": current_user.id,
        "rag_enabled": session.rag_enabled,
        "rag_strategy": session.rag_strategy,
        "created_at": now,
        "updated_at": now,
        "metadata": session.metadata or {}
    }
    
    # Insérer la session et récupérer l'ID généré par MongoDB
    result = await session_collection.insert_one(session_dict)
    session_id = str(result.inserted_id)
    
    # Retourner la réponse avec l'ID généré
    return {
        "id": session_id,
        "user_id": current_user.id,
        "title": session.title,
        "rag_enabled": session.rag_enabled,
        "rag_strategy": session.rag_strategy,
        "created_at": now,
        "updated_at": now,
        "metadata": session.metadata or {}
    }

@router.get("/sessions", response_model=List[ChatSessionResponse])
async def get_chat_sessions(
    current_user: UserInDB = Depends(get_current_active_user),
    skip: int = 0,
    limit: int = 20
) -> Any:
    """
    Récupérer toutes les sessions de chat de l'utilisateur.
    """
    session_collection = await get_chat_session_collection()
    
    # Récupérer les sessions de l'utilisateur
    cursor = session_collection.find({"user_id": current_user.id}).sort("updated_at", -1).skip(skip).limit(limit)
    
    sessions = []
    async for session in cursor:
        # Convertir les ObjectId en chaînes de caractères
        session_id = str(session["_id"])
        user_id = str(session["user_id"])
        
        # Gérer les sessions qui n'ont pas les champs rag_enabled et rag_strategy
        rag_enabled = session.get("rag_enabled", True)
        rag_strategy = session.get("rag_strategy", None)
        
        sessions.append({
            "id": session_id,
            "user_id": user_id,
            "title": session["title"],
            "rag_enabled": rag_enabled,
            "rag_strategy": rag_strategy,
            "created_at": session["created_at"],
            "updated_at": session["updated_at"],
            "metadata": session.get("metadata", {})
        })
    
    return sessions

@router.get("/sessions/{session_id}", response_model=ChatSessionResponse)
async def get_chat_session(
    session_id: str,
    current_user: UserInDB = Depends(get_current_active_user)
) -> Any:
    """
    Récupérer une session de chat spécifique.
    """
    session_collection = await get_chat_session_collection()
    
    # Essayer de trouver la session avec l'ID exact
    session = None
    
    # Essayer d'abord avec ObjectId si valide
    if ObjectId.is_valid(session_id):
        session = await session_collection.find_one({
            "_id": ObjectId(session_id),
            "user_id": current_user.id
        })
    
    # Si non trouvée, essayer avec l'ID comme chaîne
    if not session:
        session = await session_collection.find_one({
            "_id": session_id,
            "user_id": current_user.id
        })
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session de chat non trouvée"
        )
    
    # Convertir les ObjectId en chaînes de caractères
    session_id = str(session["_id"])
    user_id = str(session["user_id"])
    
    # Gérer les sessions qui n'ont pas les champs rag_enabled et rag_strategy
    rag_enabled = session.get("rag_enabled", True)
    rag_strategy = session.get("rag_strategy", None)
    
    return {
        "id": session_id,
        "user_id": user_id,
        "title": session["title"],
        "rag_enabled": rag_enabled,
        "rag_strategy": rag_strategy,
        "created_at": session["created_at"],
        "updated_at": session["updated_at"],
        "metadata": session.get("metadata", {})
    }

@router.put("/sessions/{session_id}", response_model=ChatSessionResponse)
async def update_chat_session(
    session_id: str,
    session_data: ChatSessionUpdate,
    current_user: UserInDB = Depends(get_current_active_user)
) -> Any:
    """
    Mettre à jour une session de chat.
    """
    session_collection = await get_chat_session_collection()
    
    # Essayer de trouver la session avec l'ID exact
    session = None
    
    # Essayer d'abord avec ObjectId si valide
    if ObjectId.is_valid(session_id):
        session = await session_collection.find_one({
            "_id": ObjectId(session_id),
            "user_id": current_user.id
        })
    
    # Si non trouvée, essayer avec l'ID comme chaîne
    if not session:
        session = await session_collection.find_one({
            "_id": session_id,
            "user_id": current_user.id
        })
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session de chat non trouvée"
        )
    
    update_data = {k: v for k, v in session_data.dict(exclude_unset=True).items() if v is not None}
    
    if update_data:
        update_data["updated_at"] = datetime.utcnow()
        
        # Utiliser l'ID de session tel qu'il est stocké dans MongoDB
        await session_collection.update_one(
            {"_id": session["_id"]},
            {"$set": update_data}
        )
    
    # Récupérer la session mise à jour
    updated_session = await session_collection.find_one({"_id": session["_id"]})
    
    # Convertir les ObjectId en chaînes
    session_id_str = str(updated_session["_id"])
    user_id_str = str(updated_session["user_id"])
    
    return {
        "id": session_id_str,
        "user_id": user_id_str,
        "title": updated_session["title"],
        "rag_enabled": updated_session["rag_enabled"],
        "rag_strategy": updated_session.get("rag_strategy"),
        "created_at": updated_session["created_at"],
        "updated_at": updated_session["updated_at"],
        "metadata": updated_session["metadata"]
    }

@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat_session(
    session_id: str,
    current_user: UserInDB = Depends(get_current_active_user)
) -> None:
    """
    Supprimer une session de chat et tous ses messages.
    """
    session_collection = await get_chat_session_collection()
    message_collection = await get_message_collection()
    
    # Essayer de trouver la session avec l'ID exact
    session = None
    
    # Essayer d'abord avec ObjectId si valide
    if ObjectId.is_valid(session_id):
        session = await session_collection.find_one({
            "_id": ObjectId(session_id),
            "user_id": current_user.id
        })
    
    # Si non trouvée, essayer avec l'ID comme chaîne
    if not session:
        session = await session_collection.find_one({
            "_id": session_id,
            "user_id": current_user.id
        })
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session de chat non trouvée"
        )
    
    # Supprimer tous les messages associés
    await message_collection.delete_many({"session_id": str(session["_id"])})
    
    # Supprimer la session
    await session_collection.delete_one({"_id": session["_id"]})

# Messages
@router.post("/sessions/{session_id}/messages", response_model=MessageResponse)
async def create_message(
    session_id: str,
    message: MessageCreate,
    current_user: UserInDB = Depends(get_current_active_user)
) -> Any:
    """
    Créer un nouveau message dans une session de chat.
    """
    session_collection = await get_chat_session_collection()
    
    # Essayer de trouver la session avec l'ID exact
    session = None
    
    # Essayer d'abord avec ObjectId si valide
    if ObjectId.is_valid(session_id):
        session = await session_collection.find_one({
            "_id": ObjectId(session_id),
            "user_id": current_user.id
        })
    
    # Si non trouvée, essayer avec l'ID comme chaîne
    if not session:
        session = await session_collection.find_one({
            "_id": session_id,
            "user_id": current_user.id
        })
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session de chat non trouvée"
        )
    
    # Déterminer le bon format d'ID pour la session
    session_id_for_storage = session_id
    if isinstance(session["_id"], ObjectId):
        session_id_for_storage = str(session["_id"])
    
    # Créer un nouveau message
    message_collection = await get_message_collection()
    now = datetime.utcnow()
    
    # Créer un dictionnaire de message sans spécifier l'ID
    message_dict = {
        "session_id": session_id_for_storage,
        "role": message.role,
        "content": message.content,
        "timestamp": now,
        "metadata": message.metadata or {}
    }
    
    # Insérer le message et récupérer l'ID généré par MongoDB
    result = await message_collection.insert_one(message_dict)
    message_id = str(result.inserted_id)
    
    # Mettre à jour la date de dernière modification de la session
    await session_collection.update_one(
        {"_id": session["_id"]},
        {"$set": {"updated_at": now}}
    )
    
    # Retourner la réponse avec l'ID généré
    return {
        "id": message_id,
        "session_id": session_id_for_storage,
        "role": message.role,
        "content": message.content,
        "timestamp": now,
        "metadata": message.metadata or {}
    }

@router.get("/sessions/{session_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    session_id: str,
    current_user: UserInDB = Depends(get_current_active_user),
    skip: int = 0,
    limit: int = 50
) -> Any:
    """
    Récupérer tous les messages d'une session de chat.
    """
    session_collection = await get_chat_session_collection()
    message_collection = await get_message_collection()
    
    # Essayer de trouver la session avec l'ID exact
    session = None
    
    # Essayer d'abord avec ObjectId si valide
    if ObjectId.is_valid(session_id):
        session = await session_collection.find_one({
            "_id": ObjectId(session_id),
            "user_id": current_user.id
        })
    
    # Si non trouvée, essayer avec l'ID comme chaîne
    if not session:
        session = await session_collection.find_one({
            "_id": session_id,
            "user_id": current_user.id
        })
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session de chat non trouvée"
        )
    
    # Utiliser str(session["_id"]) pour la requête de messages
    session_id_for_query = str(session["_id"])
    
    messages = []
    cursor = message_collection.find(
        {"session_id": session_id_for_query}
    ).sort("timestamp", 1).skip(skip).limit(limit)
    
    async for message in cursor:
        # Convertir les ObjectId en str si nécessaire
        message_id = str(message["_id"])
        
        messages.append({
            "id": message_id,
            "session_id": message["session_id"],
            "role": message["role"],
            "content": message["content"],
            "metadata": message["metadata"],
            "timestamp": message["timestamp"]
        })
        
    return messages

# Streaming
@router.get("/stream")
async def stream_chat(
    session_id: str,
    message: str,
    rag_enabled: bool = Query(True),
    rag_strategy: Optional[str] = Query(None),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    Stream de chat avec génération de réponse en temps réel.
    """
    try:
        # Vérifier que la session existe
        message_collection = await get_message_collection()
        session_collection = await get_chat_session_collection()
        
        # Correction importante: Convertir l'ID en ObjectId pour la recherche dans MongoDB
        # car la recherche par chaîne de caractères ne fonctionne pas
        session = None
        
        if ObjectId.is_valid(session_id):
            try:
                # Cette méthode devrait fonctionner car l'inspection a montré que les ObjectId sont bien reconnus
                session = await session_collection.find_one({
                    "_id": ObjectId(session_id),
                    "user_id": current_user.id
                })
                logger.info(f"Session trouvée avec ObjectId: {session_id}")
            except Exception as e:
                logger.error(f"Erreur lors de la recherche avec ObjectId: {e}")
        
        # Si la session n'est toujours pas trouvée, essayer d'autres méthodes
        if not session:
            logger.warning(f"Session non trouvée avec ObjectId, essai avec chaîne...")
            session = await session_collection.find_one({
                "_id": session_id,
                "user_id": current_user.id
            })
        
        if not session:
            logger.warning(f"Session non trouvée avec chaîne, essai avec champ 'id'...")
            session = await session_collection.find_one({
                "id": session_id,
                "user_id": current_user.id
            })
            
        logger.info(f"Recherche de session {session_id} pour l'utilisateur {current_user.id}: {'trouvée' if session else 'non trouvée'}")
        
        if not session:
            # Liste des IDs de session pour l'utilisateur pour aider au débogage
            cursor = session_collection.find({"user_id": current_user.id})
            user_sessions = []
            async for s in cursor:
                user_sessions.append(str(s["_id"]))
            
            logger.error(f"Session {session_id} non trouvée. Sessions disponibles pour l'utilisateur: {user_sessions}")
            
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} non trouvée"
            )
        
        # Récupérer le bon ID de session pour le stockage
        session_id_for_storage = str(session["_id"]) if "_id" in session else session_id
        
        # ID pour la réponse assistant (sera utilisé pour l'annulation)
        response_id = str(uuid.uuid4()).replace("-", "")
        
        # Signal d'annulation pour arrêter la génération
        abort_signal = asyncio.Event()
        
        # Initialiser le processeur de chat
        chat_processor = ChatProcessor()
        
        # Fonction pour générer les événements SSE
        async def event_generator():
            try:
                # Envoyer l'ID de message pour que le client puisse demander l'annulation
                yield {
                    "event": "message",
                    "data": json.dumps({"message_id": response_id})
                }
                
                # Démarrer la génération en streaming
                full_response = ""
                
                async for token in chat_processor.generate_response_stream(
                    query=message,
                    session_id=session_id_for_storage,
                    user_id=str(current_user.id),
                    abort_signal=abort_signal,
                    message_id=response_id,
                    rag_enabled=rag_enabled,
                    rag_strategy=rag_strategy
                ):
                    if token.startswith("[ERROR]"):
                        yield {
                            "event": "error",
                            "data": json.dumps({"error": token, "message_id": response_id})
                        }
                        break
                    elif token == "[CANCELLED]":
                        yield {
                            "event": "cancelled",
                            "data": json.dumps({"message_id": response_id})
                        }
                        break
                    else:
                        full_response += token
                        yield {
                            "event": "message",
                            "data": json.dumps({"token": token, "message_id": response_id})
                        }
                
                # Événement de fin
                yield {
                    "event": "done",
                    "data": json.dumps({"message_id": response_id})
                }
                
            except Exception as e:
                logger.error(f"Erreur lors du streaming: {str(e)}")
                yield {
                    "event": "error",
                    "data": json.dumps({"error": f"Erreur lors de la génération: {str(e)}", "message_id": response_id})
                }
        
        return EventSourceResponse(event_generator())
        
    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation du streaming: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la préparation du streaming: {str(e)}"
        )

@router.post("/cancel/{message_id}", response_model=CancelResponse)
async def cancel_streaming(
    message_id: str,
    current_user: UserInDB = Depends(get_current_active_user)
) -> Any:
    """
    Annule la génération d'une réponse en streaming.
    """
    try:
        # Vérifier que le message existe et appartient à l'utilisateur
        message_collection = await get_message_collection()
        message = await message_collection.find_one({"_id": message_id})
        
        if not message:
            return CancelResponse(status="not_found", message=f"Message {message_id} non trouvé")
        
        # Vérifier que l'utilisateur a accès à la session
        session_collection = await get_chat_session_collection()
        session = await session_collection.find_one({"_id": message["session_id"]})
        
        if not session or session["user_id"] != current_user.id:
            return CancelResponse(status="not_found", message="Session non trouvée ou non autorisée")
        
        # Initialiser le processeur de chat et annuler la génération
        chat_processor = ChatProcessor()
        cancelled = chat_processor.cancel_generation(message_id)
        
        if cancelled:
            # Mettre à jour le message avec l'indication d'annulation
            await message_collection.update_one(
                {"_id": message_id},
                {"$set": {
                    "content": message["content"] + " [GÉNÉRATION ANNULÉE]",
                    "metadata.status": "cancelled"
                }}
            )
            return CancelResponse(status="success", message="Génération annulée avec succès")
        else:
            return CancelResponse(status="not_found", message="Aucune génération active trouvée pour ce message")
            
    except Exception as e:
        logger.error(f"Erreur lors de l'annulation du streaming: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'annulation: {str(e)}"
        )