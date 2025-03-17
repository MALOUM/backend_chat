import os
import logging
import asyncio
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Union, AsyncGenerator, Callable

from app import config
from app.db.mongodb import get_chat_session_collection, get_message_collection
from app.models.chat import MessageRole

from app.core.chat_memory import ChatMemoryManager
from app.core.llm_streaming import StreamingManager, ModelProvider
from app.core.hf_llm import HuggingFaceLLM
from app.core.lm_studio_llm import LMStudioLLM

# Tenter d'importer OpenAI (optionnel)
try:
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

logger = logging.getLogger(__name__)

class ChatProcessor:
    """
    Processeur principal pour gérer les interactions de chat.
    Coordonne la mémoire, les modèles LLM et le streaming.
    """
    
    def __init__(self):
        """Initialise le processeur de chat"""
        self.streaming_manager = StreamingManager()
        
        # Suivi des tâches en cours
        self.active_tasks = {}
        
        logger.info("ChatProcessor initialisé")
    
    def get_llm_client(self, provider: Optional[str] = None) -> Any:
        """
        Obtient le client LLM approprié en fonction du fournisseur configuré.
        
        Args:
            provider: Fournisseur de LLM à utiliser (si None, utilise la configuration)
            
        Returns:
            Client LLM approprié
        
        Raises:
            ValueError: Si le fournisseur n'est pas supporté ou non disponible
        """
        provider = provider or config.LLM_PROVIDER
        
        if provider.lower() == "openai":
            if not OPENAI_AVAILABLE:
                raise ValueError("Le fournisseur OpenAI est configuré mais le package n'est pas installé")
            if not config.OPENAI_API_KEY:
                raise ValueError("Le fournisseur OpenAI est configuré mais OPENAI_API_KEY n'est pas défini")
            
            return AsyncOpenAI(api_key=config.OPENAI_API_KEY, model=config.LLM_MODEL)
        
        elif provider.lower() == "huggingface":
            if not config.HF_API_KEY or not config.HF_ENDPOINT:
                raise ValueError("Le fournisseur HuggingFace est configuré mais HF_API_KEY ou HF_ENDPOINT n'est pas défini")
            
            return HuggingFaceLLM(api_key=config.HF_API_KEY, endpoint=config.HF_ENDPOINT)
        
        elif provider.lower() == "lmstudio":
            return LMStudioLLM(
                base_url=config.LM_STUDIO_BASE_URL,
                api_key=config.LM_STUDIO_API_KEY,
                model=config.LM_STUDIO_MODEL
            )
        
        else:
            raise ValueError(f"Fournisseur LLM non supporté: {provider}")
    
    def get_model_provider(self, provider: Optional[str] = None) -> ModelProvider:
        """
        Obtient l'énumération ModelProvider correspondant au fournisseur.
        
        Args:
            provider: Nom du fournisseur
            
        Returns:
            Énumération ModelProvider
        """
        provider = provider or config.LLM_PROVIDER
        
        if provider.lower() == "openai":
            return ModelProvider.OPENAI
        elif provider.lower() == "huggingface":
            return ModelProvider.HUGGINGFACE
        elif provider.lower() == "lmstudio":
            return ModelProvider.LMSTUDIO
        else:
            raise ValueError(f"Fournisseur LLM non supporté: {provider}")
    
    async def generate_response(
        self,
        query: str,
        session_id: str,
        user_id: str,
        context: Optional[str] = None,
        rag_enabled: bool = True,
        rag_strategy: Optional[str] = None,
        provider: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7
    ) -> str:
        """
        Génère une réponse à une requête utilisateur.
        
        Args:
            query: Question ou requête de l'utilisateur
            session_id: ID de la session de chat
            user_id: ID de l'utilisateur
            context: Contexte supplémentaire (ex: résultats RAG)
            rag_enabled: Si True, RAG est activé pour cette requête
            rag_strategy: Stratégie RAG à utiliser
            provider: Fournisseur LLM à utiliser
            max_tokens: Nombre maximum de tokens dans la réponse
            temperature: Température de génération (créativité)
            
        Returns:
            Texte de la réponse générée
        """
        # Initialiser le gestionnaire de mémoire de conversation
        memory_manager = ChatMemoryManager(session_id, user_id)
        
        # Ajouter le message utilisateur à l'historique
        metadata = {
            "rag_enabled": rag_enabled,
            "rag_strategy": rag_strategy
        }
        await memory_manager.add_user_message(query, metadata)
        
        # Préparer les messages pour le LLM
        messages = await memory_manager.get_messages_for_llm()
        
        # Ajouter le contexte RAG si disponible
        if context and rag_enabled:
            system_msg = {
                "role": "system",
                "content": f"Utilise les informations suivantes pour répondre à la question de l'utilisateur:\n\n{context}"
            }
            messages.insert(0, system_msg)
        
        try:
            # Obtenir le client LLM approprié
            llm_client = self.get_llm_client(provider)
            
            # Choisir la méthode de génération en fonction du fournisseur
            provider_type = self.get_model_provider(provider)
            
            if provider_type == ModelProvider.OPENAI:
                # Utiliser l'API OpenAI
                response = await llm_client.chat.completions.create(
                    model=config.LLM_MODEL,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                response_text = response.choices[0].message.content
                
            elif provider_type in [ModelProvider.HUGGINGFACE, ModelProvider.LMSTUDIO]:
                # Utiliser l'implémentation spécifique
                response_text = await llm_client.generate_from_messages(
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                
            else:
                raise ValueError(f"Fournisseur non supporté: {provider}")
            
            # Enregistrer la réponse dans l'historique
            await memory_manager.add_assistant_message(response_text)
            
            return response_text
            
        except Exception as e:
            error_msg = f"Erreur lors de la génération de la réponse: {str(e)}"
            logger.error(error_msg)
            
            # Enregistrer l'erreur dans l'historique
            await memory_manager.add_assistant_message(f"[ERROR]: {error_msg}")
            
            raise
    
    async def generate_response_stream(
        self,
        query: str,
        session_id: str,
        user_id: str,
        context: Optional[str] = None,
        abort_signal: Optional[asyncio.Event] = None,
        message_id: Optional[str] = None,
        rag_enabled: bool = True,
        rag_strategy: Optional[str] = None,
        provider: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        """
        Génère une réponse en streaming à une requête utilisateur.
        
        Args:
            query: Question ou requête de l'utilisateur
            session_id: ID de la session de chat
            user_id: ID de l'utilisateur
            context: Contexte supplémentaire (ex: résultats RAG)
            abort_signal: Signal d'annulation pour interrompre la génération
            message_id: ID du message assistant (si déjà créé)
            rag_enabled: Si True, RAG est activé pour cette requête
            rag_strategy: Stratégie RAG à utiliser
            provider: Fournisseur LLM à utiliser
            max_tokens: Nombre maximum de tokens dans la réponse
            temperature: Température de génération (créativité)
            
        Yields:
            Morceaux de texte générés
            
        Raises:
            Exception: Si une erreur se produit pendant la génération
        """
        # Récupérer la collection de messages
        message_collection = await get_message_collection()
        
        # Initialiser le gestionnaire de mémoire de conversation
        memory_manager = ChatMemoryManager(session_id, user_id)
        
        # Créer un ID de message s'il n'est pas fourni
        if not message_id:
            message_id = str(uuid.uuid4()).replace("-", "")
        
        # Créer un signal d'annulation s'il n'est pas fourni
        if not abort_signal:
            abort_signal = asyncio.Event()
        
        # Ajouter le message utilisateur à l'historique
        metadata = {
            "rag_enabled": rag_enabled,
            "rag_strategy": rag_strategy
        }
        user_message = await memory_manager.add_user_message(query, metadata)
        
        # Enregistrer le message assistant vide (sera mis à jour à la fin)
        assistant_message = {
            "_id": message_id,
            "session_id": session_id,
            "role": MessageRole.ASSISTANT,
            "content": "",  # Sera mis à jour
            "timestamp": datetime.utcnow(),
            "metadata": {"streaming": True}
        }
        await message_collection.insert_one(assistant_message)
        
        # Préparer les messages pour le LLM
        messages = await memory_manager.get_messages_for_llm()
        
        # Ajouter le contexte RAG si disponible
        if context and rag_enabled:
            system_msg = {
                "role": "system",
                "content": f"Utilise les informations suivantes pour répondre à la question de l'utilisateur:\n\n{context}"
            }
            messages.insert(0, system_msg)
        
        try:
            # Obtenir le client LLM et le fournisseur
            llm_client = self.get_llm_client(provider)
            provider_type = self.get_model_provider(provider)
            
            # Créer une file d'attente pour les tokens générés
            token_queue = asyncio.Queue()
            
            # Fonction de callback pour recevoir les tokens
            full_response = ""
            
            def token_callback(token: str):
                if token:
                    nonlocal full_response
                    full_response += token
                    asyncio.create_task(token_queue.put(token))
            
            # Démarrer la génération de tokens en arrière-plan
            generation_task = asyncio.create_task(
                self.streaming_manager.stream_tokens(
                    message_id=message_id,
                    provider=provider_type,
                    llm_client=llm_client,
                    prompt_or_messages=messages,
                    callback=token_callback,
                    max_tokens=max_tokens,
                    temperature=temperature
                )
            )
            
            # Suivre la tâche
            self.active_tasks[message_id] = generation_task
            
            # Capturer les tokens et les renvoyer à travers le générateur
            try:
                while True:
                    # Attendre un token ou un signal d'annulation
                    done, pending = await asyncio.wait(
                        [asyncio.create_task(token_queue.get()), abort_signal.wait()],
                        return_when=asyncio.FIRST_COMPLETED,
                        timeout=10  # Timeout pour éviter de bloquer indéfiniment
                    )
                    
                    # Vérifier si la tâche a été annulée
                    if abort_signal.is_set():
                        logger.info(f"Génération annulée pour message_id={message_id}")
                        yield "[CANCELLED]"
                        break
                    
                    # Vérifier si nous avons un timeout
                    if not done:
                        # Si la tâche est toujours en cours, continuer d'attendre
                        if not generation_task.done():
                            logger.warning(f"Timeout en attendant des tokens pour message_id={message_id}, continuer d'attendre")
                            continue
                        # Sinon, la tâche est terminée, sortir de la boucle
                        else:
                            logger.info(f"Génération terminée pour message_id={message_id}")
                            break
                    
                    # Obtenir le token
                    token = None
                    for future in done:
                        if future.exception():
                            logger.error(f"Erreur dans la tâche: {future.exception()}")
                        else:
                            result = future.result()
                            if isinstance(result, str):
                                token = result
                    
                    # Renvoyer le token s'il est valide
                    if token:
                        yield token
                    
                    # Vérifier si la génération est terminée
                    if generation_task.done():
                        logger.info(f"Tâche de génération terminée pour message_id={message_id}")
                        if generation_task.exception():
                            logger.error(f"Exception dans la tâche de génération: {generation_task.exception()}")
                            yield f"[ERROR]: {str(generation_task.exception())}"
                        break
            
            finally:
                # Nettoyer la tâche de génération
                if message_id in self.active_tasks:
                    del self.active_tasks[message_id]
                
                # Mettre à jour le message avec la réponse complète
                if full_response:
                    await message_collection.update_one(
                        {"_id": message_id},
                        {"$set": {"content": full_response}}
                    )
        
        except Exception as e:
            error_msg = f"Erreur lors de la génération de la réponse en streaming: {str(e)}"
            logger.error(error_msg)
            
            # Mettre à jour le message avec l'erreur
            await message_collection.update_one(
                {"_id": message_id},
                {"$set": {"content": f"[ERROR]: {error_msg}", "metadata.error": str(e)}}
            )
            
            yield f"[ERROR]: {error_msg}"
            raise
    
    def cancel_generation(self, message_id: str) -> bool:
        """
        Annule une génération de réponse en cours.
        
        Args:
            message_id: ID du message à annuler
            
        Returns:
            True si la génération a été trouvée et annulée, False sinon
        """
        return self.streaming_manager.cancel_stream(message_id)
    
    def cancel_all_generations(self):
        """Annule toutes les générations en cours"""
        self.streaming_manager.cancel_all_streams()
        
    async def update_session_title(self, session_id: str, title: Optional[str] = None) -> str:
        """
        Met à jour ou génère un titre pour une session de chat.
        
        Args:
            session_id: ID de la session
            title: Titre personnalisé (si None, un titre sera généré automatiquement)
            
        Returns:
            Titre mis à jour ou généré
        """
        # Si un titre est fourni, l'utiliser directement
        if title:
            # Mettre à jour le titre dans la base de données
            session_collection = await get_chat_session_collection()
            await session_collection.update_one(
                {"_id": session_id},
                {"$set": {"title": title, "updated_at": datetime.utcnow()}}
            )
            return title
        
        # Sinon, générer un titre basé sur les messages de la session
        memory_manager = ChatMemoryManager(session_id=session_id, user_id=None)
        messages = await memory_manager.get_chat_history(exclude_system=True)
        
        # S'il n'y a pas assez de messages, utiliser un titre par défaut
        if len(messages) < 2:
            default_title = f"Nouvelle conversation ({datetime.utcnow().strftime('%Y-%m-%d %H:%M')})"
            
            # Mettre à jour le titre dans la base de données
            session_collection = await get_chat_session_collection()
            await session_collection.update_one(
                {"_id": session_id},
                {"$set": {"title": default_title, "updated_at": datetime.utcnow()}}
            )
            
            return default_title
        
        # Extraire les premiers messages pour générer un titre
        first_user_message = next((msg for msg in messages if msg["role"] == MessageRole.USER), None)
        
        if not first_user_message:
            default_title = f"Nouvelle conversation ({datetime.utcnow().strftime('%Y-%m-%d %H:%M')})"
            
            # Mettre à jour le titre dans la base de données
            session_collection = await get_chat_session_collection()
            await session_collection.update_one(
                {"_id": session_id},
                {"$set": {"title": default_title, "updated_at": datetime.utcnow()}}
            )
            
            return default_title
        
        # Créer un titre basé sur le premier message utilisateur
        # Limiter à 50 caractères pour éviter les titres trop longs
        content = first_user_message["content"]
        if len(content) > 50:
            content = content[:47] + "..."
        
        # Mettre à jour le titre dans la base de données
        session_collection = await get_chat_session_collection()
        await session_collection.update_one(
            {"_id": session_id},
            {"$set": {"title": content, "updated_at": datetime.utcnow()}}
        )
        
        return content 