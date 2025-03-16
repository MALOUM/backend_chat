from fastapi import APIRouter, HTTPException, Depends, status, Query
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
from bson import ObjectId

from app.dependencies import get_current_active_user
from app.models.user import UserInDB
from app.models.feedback import Feedback, FeedbackRating, FeedbackCategory
from app.schemas.feedback import FeedbackCreate, FeedbackUpdate, FeedbackResponse, FeedbackStats
from app.db.mongodb import get_feedback_collection, get_message_collection, get_chat_session_collection

router = APIRouter(prefix="/feedback", tags=["Feedback"])

@router.post("", response_model=FeedbackResponse)
async def create_feedback(
    feedback_data: FeedbackCreate,
    current_user: UserInDB = Depends(get_current_active_user)
) -> Any:
    """
    Créer un nouveau feedback sur une réponse du système.
    """
    feedback_collection = await get_feedback_collection()
    message_collection = await get_message_collection()

    # Vérifier que le message existe
    message = await message_collection.find_one({"_id": feedback_data.message_id})
    
    # Si non trouvé, essayer avec un ObjectId
    if not message:
        try:
            if ObjectId.is_valid(feedback_data.message_id):
                message = await message_collection.find_one({"_id": ObjectId(feedback_data.message_id)})
        except Exception as e:
            print(f"Erreur lors de la conversion de l'ID du message en ObjectId: {e}")
            
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message non trouvé"
        )
    
    # Récupérer la session_id du message
    session_id = message["session_id"]
    
    # Vérifier si un feedback existe déjà pour ce message
    existing_feedback = await feedback_collection.find_one({
        "user_id": current_user.id,
        "message_id": feedback_data.message_id
    })
    
    if existing_feedback:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Un feedback existe déjà pour ce message"
        )
    
    now = datetime.utcnow()
    
    # Créer un dictionnaire de feedback sans spécifier l'ID
    feedback_dict = {
        "user_id": current_user.id,
        "message_id": feedback_data.message_id,
        "session_id": session_id,
        "rating": feedback_data.rating,
        "category": feedback_data.category,
        "comment": feedback_data.comment,
        "timestamp": now,
        "metadata": feedback_data.metadata or {}
    }
    
    # Insérer sans spécifier l'ID pour laisser MongoDB le générer
    result = await feedback_collection.insert_one(feedback_dict)
    
    # Utiliser l'ID généré par MongoDB
    feedback_id = str(result.inserted_id)
    
    return {
        "id": feedback_id,
        "user_id": current_user.id,
        "message_id": feedback_data.message_id,
        "session_id": session_id,
        "rating": feedback_data.rating,
        "category": feedback_data.category,
        "comment": feedback_data.comment,
        "timestamp": now,
        "metadata": feedback_data.metadata or {}
    }

@router.get("", response_model=List[FeedbackResponse])
async def get_user_feedbacks(
    current_user: UserInDB = Depends(get_current_active_user),
    session_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 50
) -> Any:
    """
    Récupérer les feedbacks de l'utilisateur, avec filtrage optionnel par session.
    """
    feedback_collection = await get_feedback_collection()
    
    query = {"user_id": current_user.id}
    if session_id:
        # Essayer d'abord avec ObjectId si valide
        if ObjectId.is_valid(session_id):
            query["session_id"] = str(ObjectId(session_id))
        else:
            query["session_id"] = session_id
    
    feedbacks = []
    cursor = feedback_collection.find(query).sort("timestamp", -1).skip(skip).limit(limit)
    
    async for feedback in cursor:
        # Convertir les ObjectId en chaînes de caractères
        feedback_id = str(feedback["_id"])
        user_id = str(feedback["user_id"])
        message_id = str(feedback["message_id"])
        sess_id = str(feedback["session_id"])
        
        feedbacks.append({
            "id": feedback_id,
            "user_id": user_id,
            "message_id": message_id,
            "session_id": sess_id,
            "rating": feedback["rating"],
            "category": feedback["category"],
            "comment": feedback["comment"],
            "timestamp": feedback["timestamp"],
            "metadata": feedback["metadata"]
        })
    
    return feedbacks

@router.get("/message/{message_id}", response_model=FeedbackResponse)
async def get_message_feedback(
    message_id: str,
    current_user: UserInDB = Depends(get_current_active_user)
) -> Any:
    """
    Récupérer le feedback pour un message spécifique.
    """
    feedback_collection = await get_feedback_collection()
    
    # Essayer d'abord avec le message_id tel quel
    feedback = None
    
    # Si le message_id est un ObjectId valide, essayer de le convertir
    if ObjectId.is_valid(message_id):
        feedback = await feedback_collection.find_one({
            "message_id": str(ObjectId(message_id)),
            "user_id": current_user.id
        })
    
    # Si non trouvé, essayer avec le message_id tel quel
    if not feedback:
        feedback = await feedback_collection.find_one({
            "message_id": message_id,
            "user_id": current_user.id
        })
    
    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feedback non trouvé"
        )
    
    # Convertir les ObjectId en chaînes de caractères
    feedback_id = str(feedback["_id"])
    user_id = str(feedback["user_id"])
    msg_id = str(feedback["message_id"])
    session_id = str(feedback["session_id"])
    
    return {
        "id": feedback_id,
        "user_id": user_id,
        "message_id": msg_id,
        "session_id": session_id,
        "rating": feedback["rating"],
        "category": feedback["category"],
        "comment": feedback["comment"],
        "timestamp": feedback["timestamp"],
        "metadata": feedback["metadata"]
    }

@router.put("/{feedback_id}", response_model=FeedbackResponse)
async def update_feedback(
    feedback_id: str,
    feedback_data: FeedbackUpdate,
    current_user: UserInDB = Depends(get_current_active_user)
) -> Any:
    """
    Mettre à jour un feedback existant.
    """
    feedback_collection = await get_feedback_collection()
    
    # Essayer d'abord avec le feedback_id tel quel
    feedback = None
    
    # Si le feedback_id est un ObjectId valide, essayer de le convertir
    if ObjectId.is_valid(feedback_id):
        feedback = await feedback_collection.find_one({
            "_id": ObjectId(feedback_id),
            "user_id": current_user.id
        })
    
    # Si non trouvé, essayer avec le feedback_id tel quel
    if not feedback:
        feedback = await feedback_collection.find_one({
            "_id": feedback_id,
            "user_id": current_user.id
        })
    
    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feedback non trouvé"
        )
    
    update_data = {k: v for k, v in feedback_data.dict(exclude_unset=True).items() if v is not None}
    
    if update_data:
        # Utiliser l'ID tel qu'il est stocké dans MongoDB
        feedback_id_for_update = feedback["_id"]
        if isinstance(feedback_id_for_update, str) and ObjectId.is_valid(feedback_id_for_update):
            feedback_id_for_update = ObjectId(feedback_id_for_update)
        
        await feedback_collection.update_one(
            {"_id": feedback_id_for_update},
            {"$set": update_data}
        )
    
    # Récupérer le feedback mis à jour
    updated_feedback = await feedback_collection.find_one({"_id": feedback["_id"]})
    
    # Convertir les ObjectId en chaînes de caractères
    feedback_id = str(updated_feedback["_id"])
    user_id = str(updated_feedback["user_id"])
    message_id = str(updated_feedback["message_id"])
    session_id = str(updated_feedback["session_id"])
    
    return {
        "id": feedback_id,
        "user_id": user_id,
        "message_id": message_id,
        "session_id": session_id,
        "rating": updated_feedback["rating"],
        "category": updated_feedback["category"],
        "comment": updated_feedback["comment"],
        "timestamp": updated_feedback["timestamp"],
        "metadata": updated_feedback["metadata"]
    }

@router.delete("/{feedback_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_feedback(
    feedback_id: str,
    current_user: UserInDB = Depends(get_current_active_user)
) -> None:
    """
    Supprimer un feedback.
    """
    feedback_collection = await get_feedback_collection()
    
    print(f"Tentative de suppression du feedback avec ID: {feedback_id}")
    
    # Essayer d'abord avec le feedback_id tel quel
    feedback = None
    
    # Si le feedback_id est un ObjectId valide, essayer de le convertir
    if ObjectId.is_valid(feedback_id):
        print(f"ID valide pour ObjectId, recherche avec ObjectId({feedback_id})")
        feedback = await feedback_collection.find_one({
            "_id": ObjectId(feedback_id),
            "user_id": current_user.id
        })
    
    # Si non trouvé, essayer avec le feedback_id tel quel
    if not feedback:
        print(f"Recherche avec l'ID tel quel: {feedback_id}")
        feedback = await feedback_collection.find_one({
            "_id": feedback_id,
            "user_id": current_user.id
        })
    
    if not feedback:
        print(f"Feedback non trouvé pour l'ID: {feedback_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feedback non trouvé"
        )
    
    print(f"Feedback trouvé: {feedback}")
    
    # Supprimer le feedback en utilisant le bon format d'ID
    feedback_id_for_deletion = feedback["_id"]
    if isinstance(feedback_id_for_deletion, str) and ObjectId.is_valid(feedback_id_for_deletion):
        feedback_id_for_deletion = ObjectId(feedback_id_for_deletion)
    
    print(f"Suppression avec ID: {feedback_id_for_deletion}")
    result = await feedback_collection.delete_one({"_id": feedback_id_for_deletion})
    print(f"Résultat de la suppression: {result.deleted_count} document(s) supprimé(s)")

@router.get("/session/{session_id}", response_model=List[FeedbackResponse])
async def get_session_feedbacks(
    session_id: str,
    current_user: UserInDB = Depends(get_current_active_user),
    skip: int = 0,
    limit: int = 50
) -> Any:
    """
    Récupérer tous les feedbacks pour une session spécifique.
    """
    feedback_collection = await get_feedback_collection()
    
    # Construire la requête en fonction du format de l'ID
    query = {}
    
    # Si le session_id est un ObjectId valide, essayer de le convertir
    if ObjectId.is_valid(session_id):
        query["session_id"] = str(ObjectId(session_id))
    else:
        query["session_id"] = session_id
    
    feedbacks = []
    cursor = feedback_collection.find(query).sort("timestamp", -1).skip(skip).limit(limit)
    
    async for feedback in cursor:
        # Convertir les ObjectId en chaînes de caractères
        feedback_id = str(feedback["_id"])
        user_id = str(feedback["user_id"])
        message_id = str(feedback["message_id"])
        sess_id = str(feedback["session_id"])
        
        feedbacks.append({
            "id": feedback_id,
            "user_id": user_id,
            "message_id": message_id,
            "session_id": sess_id,
            "rating": feedback["rating"],
            "category": feedback["category"],
            "comment": feedback["comment"],
            "timestamp": feedback["timestamp"],
            "metadata": feedback["metadata"]
        })
    
    return feedbacks

@router.get("/stats", response_model=FeedbackStats)
async def get_feedback_stats(
    current_user: UserInDB = Depends(get_current_active_user),
    session_id: Optional[str] = None
) -> Any:
    """
    Obtenir des statistiques sur les feedbacks (pour l'utilisateur courant ou pour une session spécifique).
    """
    feedback_collection = await get_feedback_collection()
    
    # Construire la requête en fonction des paramètres
    query = {"user_id": current_user.id}
    if session_id:
        query["session_id"] = session_id
    
    # Récupérer tous les feedbacks correspondant à la requête
    feedbacks = []
    cursor = feedback_collection.find(query)
    async for feedback in cursor:
        feedbacks.append(feedback)
    
    total_count = len(feedbacks)
    
    # Si aucun feedback, retourner des statistiques vides
    if total_count == 0:
        return {
            "total_count": 0,
            "average_rating": 0.0,
            "ratings_distribution": {},
            "category_distribution": {}
        }
    
    # Calculer la distribution des notes
    ratings_distribution = {}
    for rating in FeedbackRating:
        ratings_distribution[rating.value] = 0
    
    # Calculer la distribution des catégories
    category_distribution = {}
    for category in FeedbackCategory:
        category_distribution[category.value] = 0
    
    # Parcourir les feedbacks pour calculer les statistiques
    rating_values = {
        FeedbackRating.VERY_POOR.value: 1,
        FeedbackRating.POOR.value: 2,
        FeedbackRating.NEUTRAL.value: 3,
        FeedbackRating.GOOD.value: 4,
        FeedbackRating.VERY_GOOD.value: 5
    }
    
    rating_sum = 0
    
    for feedback in feedbacks:
        rating = feedback["rating"]
        category = feedback["category"]
        
        ratings_distribution[rating] += 1
        category_distribution[category] += 1
        rating_sum += rating_values.get(rating, 3)
    
    average_rating = rating_sum / total_count
    
    return {
        "total_count": total_count,
        "average_rating": round(average_rating, 2),
        "ratings_distribution": ratings_distribution,
        "category_distribution": category_distribution
    } 