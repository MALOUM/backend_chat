import logging
import asyncio
from typing import Dict, Any, List, Callable, Optional, AsyncGenerator
import json
from enum import Enum

logger = logging.getLogger(__name__)

class ModelProvider(str, Enum):
    """Fournisseurs de modèles LLM supportés"""
    OPENAI = "openai"
    HUGGINGFACE = "huggingface"
    LMSTUDIO = "lmstudio"

class StreamingManager:
    """
    Gestionnaire de streaming pour différents modèles LLM.
    Fournit une interface unifiée pour le streaming de réponses.
    """
    
    def __init__(self):
        """Initialise le gestionnaire de streaming"""
        self.active_streams = {}
        logger.info("StreamingManager initialisé")
    
    def register_stream(self, message_id: str, abort_signal: asyncio.Event = None) -> asyncio.Event:
        """
        Enregistre un nouveau stream et retourne un signal d'annulation.
        
        Args:
            message_id: ID unique du message en cours de génération
            abort_signal: Signal d'annulation existant à utiliser (facultatif)
            
        Returns:
            Signal d'annulation pour ce stream
        """
        if abort_signal is None:
            abort_signal = asyncio.Event()
        
        self.active_streams[message_id] = abort_signal
        logger.debug(f"Stream enregistré pour message_id={message_id}")
        return abort_signal
    
    def unregister_stream(self, message_id: str):
        """
        Supprime un stream de la liste des streams actifs.
        
        Args:
            message_id: ID du message à supprimer
        """
        if message_id in self.active_streams:
            self.active_streams.pop(message_id)
            logger.debug(f"Stream supprimé pour message_id={message_id}")
    
    def cancel_stream(self, message_id: str) -> bool:
        """
        Annule un stream en cours.
        
        Args:
            message_id: ID du message à annuler
            
        Returns:
            True si le stream a été trouvé et annulé, False sinon
        """
        if message_id in self.active_streams:
            logger.info(f"Annulation du stream pour message_id={message_id}")
            self.active_streams[message_id].set()
            return True
        logger.warning(f"Tentative d'annulation d'un stream inexistant: message_id={message_id}")
        return False
    
    def cancel_all_streams(self):
        """Annule tous les streams actifs"""
        logger.info(f"Annulation de tous les streams actifs ({len(self.active_streams)})")
        for abort_signal in self.active_streams.values():
            abort_signal.set()
        self.active_streams.clear()
    
    async def stream_tokens(
        self,
        message_id: str,
        provider: ModelProvider,
        llm_client: Any,
        prompt_or_messages: Any,
        callback: Callable[[str], None],
        max_tokens: int = 1024,
        temperature: float = 0.7
    ) -> str:
        """
        Gère le streaming de tokens à partir d'un LLM et envoie chaque token via le callback.
        
        Args:
            message_id: ID unique du message
            provider: Fournisseur du modèle LLM (OpenAI, HuggingFace, etc.)
            llm_client: Client LLM à utiliser
            prompt_or_messages: Prompt texte ou liste de messages pour le LLM
            callback: Fonction de rappel à appeler pour chaque token généré
            max_tokens: Nombre maximum de tokens à générer
            temperature: Température de génération (créativité)
            
        Returns:
            Le texte complet généré
        
        Raises:
            Exception: Si une erreur se produit pendant la génération
        """
        abort_signal = self.register_stream(message_id)
        full_response = ""
        
        try:
            # Vérifier quel fournisseur utiliser
            if provider == ModelProvider.OPENAI:
                async for chunk in self._stream_openai(
                    llm_client, prompt_or_messages, abort_signal, max_tokens, temperature
                ):
                    if abort_signal.is_set():
                        callback("[CANCELLED]")
                        logger.info(f"Stream annulé pour message_id={message_id}")
                        break
                    
                    if chunk:
                        full_response += chunk
                        callback(chunk)
            
            elif provider == ModelProvider.HUGGINGFACE or provider == ModelProvider.LMSTUDIO:
                # Pour HuggingFace et LMStudio, nous utilisons leurs méthodes de streaming spécifiques
                try:
                    # Ces fournisseurs ont une méthode generate_streaming qui prend un callback
                    await llm_client.generate_streaming(
                        prompt_or_messages, 
                        callback=callback,
                        max_tokens=max_tokens,
                        temperature=temperature
                    )
                    # Obtenir la réponse complète pour la retourner
                    full_response = await self._get_full_response_from_callback_provider(
                        callback
                    )
                except Exception as e:
                    logger.error(f"Erreur lors du streaming avec {provider}: {str(e)}")
                    # Envoyer l'erreur au client
                    callback(f"[ERROR]: {str(e)}")
                    raise
            
            else:
                error_msg = f"Fournisseur non supporté: {provider}"
                logger.error(error_msg)
                callback(f"[ERROR]: {error_msg}")
                raise ValueError(error_msg)
            
        except asyncio.CancelledError:
            logger.info(f"Tâche de streaming annulée pour message_id={message_id}")
            callback("[CANCELLED]")
        
        except Exception as e:
            logger.error(f"Erreur lors du streaming pour message_id={message_id}: {str(e)}")
            callback(f"[ERROR]: {str(e)}")
            raise
        
        finally:
            # Assurer un nettoyage correct
            self.unregister_stream(message_id)
        
        return full_response
    
    async def _stream_openai(
        self, 
        client, 
        messages, 
        abort_signal: asyncio.Event,
        max_tokens: int,
        temperature: float
    ) -> AsyncGenerator[str, None]:
        """
        Méthode spécifique pour le streaming avec OpenAI.
        
        Args:
            client: Client OpenAI
            messages: Messages à envoyer
            abort_signal: Signal pour annuler le streaming
            max_tokens: Nombre maximum de tokens à générer
            temperature: Température de génération
            
        Yields:
            Chunks de texte générés
        """
        try:
            stream = await client.chat.completions.create(
                model=client.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True,
            )
            
            async for chunk in stream:
                if abort_signal.is_set():
                    break
                
                if hasattr(chunk.choices[0], 'delta') and hasattr(chunk.choices[0].delta, 'content'):
                    content = chunk.choices[0].delta.content
                    if content:
                        yield content
                
                # Pause courte pour permettre à d'autres tâches de s'exécuter
                await asyncio.sleep(0.01)
                
        except Exception as e:
            logger.error(f"Erreur dans _stream_openai: {str(e)}")
            raise
    
    async def _get_full_response_from_callback_provider(self, callback: Callable) -> str:
        """
        Pour les providers qui utilisent un callback mais ne retournent pas le texte complet,
        nous devons capturer le texte complet nous-mêmes.
        
        Args:
            callback: Fonction de callback pour le streaming
            
        Returns:
            Texte complet généré
        """
        # Cette implémentation simplifiée n'est qu'une approximation
        # En production, il faudrait probablement modifier les implémentations de callback
        # pour qu'elles accumulent également le texte généré
        
        # Pour l'instant, nous allons juste retourner une chaîne vide, car le texte complet
        # sera récupéré directement des messages dans la base de données
        return "" 