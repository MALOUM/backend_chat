import os
import logging
import json
import asyncio
from typing import Dict, Any, List, Callable, Optional, Union, Generator, AsyncGenerator

import httpx
from app import config

logger = logging.getLogger(__name__)

class LMStudioLLM:
    """
    Client pour LM Studio, qui fournit une API compatible avec OpenAI.
    Permet d'interagir avec des modèles locaux via LM Studio.
    """
    
    def __init__(
        self, 
        base_url: str = None, 
        api_key: str = None, 
        model: str = None
    ):
        """
        Initialise le client LM Studio.
        
        Args:
            base_url: URL de base de l'API LM Studio (par défaut, utilisera LM_STUDIO_BASE_URL de l'environnement)
            api_key: Clé API LM Studio (par défaut, utilisera LM_STUDIO_API_KEY de l'environnement)
            model: Nom du modèle à utiliser (par défaut, utilisera LM_STUDIO_MODEL de l'environnement)
        """
        self.base_url = base_url or config.LM_STUDIO_BASE_URL
        self.api_key = api_key or config.LM_STUDIO_API_KEY
        self.model = model or config.LM_STUDIO_MODEL
        
        if not self.base_url:
            logger.warning("Aucune URL de base LM Studio fournie. Utilisation de l'URL par défaut: http://localhost:1234/v1")
            self.base_url = "http://localhost:1234/v1"
        
        logger.info(f"LMStudioLLM initialisé avec base_url: {self.base_url}, model: {self.model}")
    
    async def generate(
        self, 
        prompt: str, 
        max_tokens: int = 1024, 
        temperature: float = 0.7
    ) -> str:
        """
        Génère une réponse à partir d'un prompt texte.
        
        Args:
            prompt: Texte du prompt
            max_tokens: Nombre maximum de tokens à générer
            temperature: Température de génération (créativité)
            
        Returns:
            Texte généré par le modèle
        """
        try:
            logger.debug(f"Génération de texte avec prompt: {prompt[:50]}...")
            
            # Préparer la requête pour l'API LM Studio (compatible OpenAI)
            headers = {
                "Content-Type": "application/json"
            }
            
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            payload = {
                "model": self.model,
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": temperature
            }
            
            # Effectuer la requête HTTP
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/completions",
                    json=payload,
                    headers=headers,
                    timeout=60.0  # Délai d'attente plus long pour les grands modèles
                )
                
                if response.status_code != 200:
                    error_msg = f"Erreur API LM Studio: {response.status_code}, {response.text}"
                    logger.error(error_msg)
                    raise Exception(error_msg)
                
                result = response.json()
                
                # Extraire le texte généré
                text = result.get("choices", [{}])[0].get("text", "")
                
                logger.debug(f"Texte généré: {text[:50]}...")
                return text
                
        except Exception as e:
            logger.error(f"Erreur lors de la génération de texte: {str(e)}")
            raise
    
    async def generate_from_messages(
        self, 
        messages: List[Dict[str, str]], 
        max_tokens: int = 1024, 
        temperature: float = 0.7
    ) -> str:
        """
        Génère une réponse à partir d'une liste de messages.
        
        Args:
            messages: Liste de messages au format {"role": "...", "content": "..."}
            max_tokens: Nombre maximum de tokens à générer
            temperature: Température de génération (créativité)
            
        Returns:
            Texte généré par le modèle
        """
        try:
            logger.debug(f"Génération de texte à partir de messages: {len(messages)} messages")
            
            # Préparer la requête pour l'API LM Studio (compatible OpenAI)
            headers = {
                "Content-Type": "application/json"
            }
            
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            payload = {
                "model": self.model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature
            }
            
            # Effectuer la requête HTTP
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=60.0  # Délai d'attente plus long pour les grands modèles
                )
                
                if response.status_code != 200:
                    error_msg = f"Erreur API LM Studio: {response.status_code}, {response.text}"
                    logger.error(error_msg)
                    raise Exception(error_msg)
                
                result = response.json()
                
                # Extraire le texte généré
                text = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                
                logger.debug(f"Texte généré: {text[:50]}...")
                return text
                
        except Exception as e:
            logger.error(f"Erreur lors de la génération de texte à partir de messages: {str(e)}")
            raise
    
    async def generate_streaming(
        self, 
        prompt_or_messages: Union[str, List[Dict[str, str]]], 
        callback: Callable[[str], None],
        max_tokens: int = 1024, 
        temperature: float = 0.7
    ) -> None:
        """
        Génère une réponse en streaming et envoie chaque morceau via le callback.
        
        Args:
            prompt_or_messages: Texte du prompt ou liste de messages
            callback: Fonction de rappel à appeler pour chaque morceau généré
            max_tokens: Nombre maximum de tokens à générer
            temperature: Température de génération (créativité)
            
        Note:
            Cette méthode ne retourne pas la réponse complète, elle l'envoie par morceaux via le callback.
        """
        try:
            # Déterminer si nous avons un prompt texte ou une liste de messages
            is_messages = isinstance(prompt_or_messages, list)
            
            # Préparer la requête pour l'API LM Studio (compatible OpenAI)
            headers = {
                "Content-Type": "application/json",
                "Accept": "text/event-stream"
            }
            
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            # Construire le payload selon le type d'entrée
            if is_messages:
                logger.debug(f"Génération de texte en streaming à partir de messages: {len(prompt_or_messages)} messages")
                payload = {
                    "model": self.model,
                    "messages": prompt_or_messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "stream": True
                }
                url = f"{self.base_url}/chat/completions"
            else:
                logger.debug(f"Génération de texte en streaming avec prompt: {prompt_or_messages[:50]}...")
                payload = {
                    "model": self.model,
                    "prompt": prompt_or_messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "stream": True
                }
                url = f"{self.base_url}/completions"
            
            # Fonction pour traiter les données SSE
            async def process_stream():
                async with httpx.AsyncClient(timeout=None) as client:
                    async with client.stream("POST", url, json=payload, headers=headers) as response:
                        if response.status_code != 200:
                            error_msg = f"Erreur API LM Studio: {response.status_code}"
                            logger.error(error_msg)
                            callback(f"[ERROR]: {error_msg}")
                            return
                        
                        async for line in response.aiter_lines():
                            if not line.strip() or line.strip() == "data: [DONE]":
                                continue
                            
                            if line.startswith("data: "):
                                try:
                                    json_data = json.loads(line[6:])
                                    
                                    if is_messages:
                                        content = json_data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                    else:
                                        content = json_data.get("choices", [{}])[0].get("text", "")
                                    
                                    if content:
                                        callback(content)
                                except json.JSONDecodeError as e:
                                    logger.warning(f"Erreur de décodage JSON: {str(e)}, ligne: {line}")
                                except Exception as e:
                                    logger.error(f"Erreur lors du traitement de la ligne: {str(e)}")
            
            # Exécuter le traitement du stream
            await process_stream()
            
        except Exception as e:
            error_msg = f"Erreur lors de la génération de texte en streaming: {str(e)}"
            logger.error(error_msg)
            # Envoyer l'erreur au client
            callback(f"[ERROR]: {error_msg}")
            raise 