import logging
import tiktoken
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.db.mongodb import get_message_collection
from app.models.chat import MessageRole

logger = logging.getLogger(__name__)

# Modèle de tokenisation à utiliser (compatible avec les modèles GPT)
ENCODING_MODEL = "cl100k_base"  # Modèle compatible avec GPT-4 et GPT-3.5

def count_tokens(text: str) -> int:
    """
    Compte le nombre de tokens dans un texte en utilisant le modèle de tokenisation spécifié.
    
    Args:
        text: Le texte à tokeniser
        
    Returns:
        Le nombre de tokens
    """
    try:
        encoding = tiktoken.get_encoding(ENCODING_MODEL)
        return len(encoding.encode(text))
    except Exception as e:
        logger.warning(f"Erreur lors du comptage des tokens: {e}. Utilisation d'une approximation.")
        # En cas d'erreur, utiliser une approximation (4 caractères ~ 1 token)
        return len(text) // 4

class ChatMemoryManager:
    """
    Gestionnaire de mémoire pour les conversations chat qui limite le nombre de tokens.
    Similaire au ConversationTokenBufferMemory de LangChain.
    """
    
    def __init__(self, session_id: str, user_id: str, max_token_limit: int = 4000):
        """
        Initialise le gestionnaire de mémoire de conversation.
        
        Args:
            session_id: ID de la session de chat
            user_id: ID de l'utilisateur
            max_token_limit: Nombre maximum de tokens à conserver en mémoire
        """
        self.session_id = session_id
        self.user_id = user_id
        self.max_token_limit = max_token_limit
        logger.info(f"Initialisation de ChatMemoryManager pour session_id={session_id} avec limite de {max_token_limit} tokens")
    
    async def get_chat_history(self, exclude_system: bool = True) -> List[Dict[str, Any]]:
        """
        Récupère l'historique de la conversation en tenant compte de la limite de tokens.
        
        Args:
            exclude_system: Si True, exclut les messages système de l'historique
            
        Returns:
            Liste des messages de l'historique respectant la limite de tokens
        """
        message_collection = await get_message_collection()
        
        # Récupérer tous les messages de la session, du plus récent au plus ancien
        query = {"session_id": self.session_id}
        if exclude_system:
            query["role"] = {"$ne": MessageRole.SYSTEM}
            
        cursor = message_collection.find(query).sort("timestamp", -1)
        messages = await cursor.to_list(length=None)
        
        # Inverser pour obtenir l'ordre chronologique
        messages.reverse()
        
        # Appliquer la limite de tokens
        return self._truncate_history_by_tokens(messages)
    
    def _truncate_history_by_tokens(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Tronque l'historique des messages pour respecter la limite de tokens.
        Conserve les messages les plus récents.
        
        Args:
            messages: Liste des messages à tronquer
            
        Returns:
            Liste tronquée des messages
        """
        # Si pas de messages, retourner une liste vide
        if not messages:
            return []
        
        # Compter les tokens dans tous les messages
        running_token_count = 0
        truncated_messages = []
        
        # Parcourir les messages du plus ancien au plus récent
        for message in messages:
            # Calculer le nombre de tokens dans ce message
            message_tokens = count_tokens(message.get("content", ""))
            
            # Si l'ajout de ce message dépasse la limite, arrêter
            if running_token_count + message_tokens > self.max_token_limit and truncated_messages:
                logger.debug(f"Limite de tokens atteinte: {running_token_count}/{self.max_token_limit}")
                break
                
            # Ajouter le message à l'historique tronqué
            truncated_messages.append(message)
            running_token_count += message_tokens
        
        # Si l'historique a été tronqué, enregistrer l'information
        if len(truncated_messages) < len(messages):
            logger.info(f"Historique tronqué: {len(truncated_messages)}/{len(messages)} messages conservés, {running_token_count} tokens")
        
        return truncated_messages
    
    async def add_user_message(self, content: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Ajoute un message utilisateur à la mémoire.
        
        Args:
            content: Le contenu du message
            metadata: Métadonnées associées au message
        
        Returns:
            Le message créé
        """
        if metadata is None:
            metadata = {}
            
        message_collection = await get_message_collection()
        
        # Créer le message
        message = {
            "session_id": self.session_id,
            "role": MessageRole.USER,
            "content": content,
            "timestamp": datetime.utcnow(),
            "metadata": metadata
        }
        
        # Insérer le message dans la base de données
        result = await message_collection.insert_one(message)
        message["_id"] = result.inserted_id
        
        logger.debug(f"Message utilisateur ajouté: {content[:50]}...")
        return message
    
    async def add_assistant_message(self, content: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Ajoute un message assistant à la mémoire.
        
        Args:
            content: Le contenu du message
            metadata: Métadonnées associées au message
        
        Returns:
            Le message créé
        """
        if metadata is None:
            metadata = {}
            
        message_collection = await get_message_collection()
        
        # Créer le message
        message = {
            "session_id": self.session_id,
            "role": MessageRole.ASSISTANT,
            "content": content,
            "timestamp": datetime.utcnow(),
            "metadata": metadata
        }
        
        # Insérer le message dans la base de données
        result = await message_collection.insert_one(message)
        message["_id"] = result.inserted_id
        
        logger.debug(f"Message assistant ajouté: {content[:50]}...")
        return message
    
    async def add_system_message(self, content: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Ajoute un message système à la mémoire.
        
        Args:
            content: Le contenu du message
            metadata: Métadonnées associées au message
        
        Returns:
            Le message créé
        """
        if metadata is None:
            metadata = {}
            
        message_collection = await get_message_collection()
        
        # Créer le message
        message = {
            "session_id": self.session_id,
            "role": MessageRole.SYSTEM,
            "content": content,
            "timestamp": datetime.utcnow(),
            "metadata": metadata
        }
        
        # Insérer le message dans la base de données
        result = await message_collection.insert_one(message)
        message["_id"] = result.inserted_id
        
        logger.debug(f"Message système ajouté: {content[:50]}...")
        return message
    
    async def get_messages_for_llm(self, system_prompt: Optional[str] = None) -> List[Dict[str, str]]:
        """
        Récupère les messages formatés pour les LLM (format compatible avec OpenAI, etc.)
        
        Args:
            system_prompt: Prompt système à ajouter en début de conversation
            
        Returns:
            Liste de messages au format {"role": "...", "content": "..."}
        """
        history = await self.get_chat_history(exclude_system=False)
        
        # Formater les messages pour le LLM
        formatted_messages = []
        
        # Ajouter le prompt système en premier s'il est fourni
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})
        
        # Ajouter les messages de l'historique
        for message in history:
            role = message["role"].lower()
            # Convertir le rôle au format attendu par les API LLM
            if role == MessageRole.USER:
                role = "user"
            elif role == MessageRole.ASSISTANT:
                role = "assistant"
            elif role == MessageRole.SYSTEM:
                role = "system"
            
            formatted_messages.append({
                "role": role,
                "content": message["content"]
            })
        
        return formatted_messages 