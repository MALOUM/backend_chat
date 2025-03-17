import os
import logging
import asyncio
from typing import Dict, Any, List, Callable, Optional, Union

import httpx
from app import config

logger = logging.getLogger(__name__)

class HuggingFaceLLM:
    """
    Client pour l'API Hugging Face Inference.
    Permet d'interagir avec les modèles hébergés sur Hugging Face.
    """
    
    def __init__(self, api_key: str = None, endpoint: str = None):
        """
        Initialise le client Hugging Face.
        
        Args:
            api_key: Clé API Hugging Face (par défaut, utilisera HF_API_KEY de l'environnement)
            endpoint: URL de l'endpoint API (par défaut, utilisera HF_ENDPOINT de l'environnement)
        """
        self.api_key = api_key or config.HF_API_KEY
        self.endpoint = endpoint or config.HF_ENDPOINT
        
        if not self.api_key:
            logger.warning("Aucune clé API Hugging Face fournie. Certaines fonctionnalités pourraient ne pas fonctionner.")
        
        if not self.endpoint:
            logger.warning("Aucun endpoint Hugging Face fourni. Utilisation des modèles publics uniquement.")
        
        logger.info(f"HuggingFaceLLM initialisé avec endpoint: {self.endpoint}")
    
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
            
            # Préparer la requête pour l'API Hugging Face
            headers = {"Authorization": f"Bearer {self.api_key}"}
            
            payload = {
                "inputs": prompt,
                "parameters": {
                    "max_new_tokens": max_tokens,
                    "temperature": temperature,
                    "do_sample": temperature > 0,
                    "return_full_text": False
                }
            }
            
            # Effectuer la requête HTTP
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.endpoint,
                    json=payload,
                    headers=headers,
                    timeout=60.0  # Délai d'attente plus long pour les grands modèles
                )
                
                if response.status_code != 200:
                    error_msg = f"Erreur API Hugging Face: {response.status_code}, {response.text}"
                    logger.error(error_msg)
                    raise Exception(error_msg)
                
                result = response.json()
                
                # L'API peut retourner soit une liste de résultats, soit un seul résultat
                if isinstance(result, list):
                    text = result[0].get("generated_text", "")
                else:
                    text = result.get("generated_text", "")
                
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
        # Convertir les messages en un prompt texte
        prompt = self._convert_messages_to_prompt(messages)
        
        # Générer la réponse
        return await self.generate(prompt, max_tokens, temperature)
    
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
            # Convertir les messages en prompt si nécessaire
            prompt = prompt_or_messages
            if isinstance(prompt_or_messages, list):
                prompt = self._convert_messages_to_prompt(prompt_or_messages)
            
            logger.debug(f"Génération de texte en streaming avec prompt: {prompt[:50]}...")
            
            # Nous simulons le streaming car l'API Hugging Face ne supporte pas nativement le streaming
            # pour tous les modèles. Dans une implémentation réelle, vous pourriez utiliser 
            # l'API streaming si disponible.
            
            # Générer la réponse complète
            full_response = await self.generate(prompt, max_tokens, temperature)
            
            # Simuler le streaming en envoyant des morceaux de texte
            chunk_size = 5  # Nombre de caractères par morceau
            
            for i in range(0, len(full_response), chunk_size):
                chunk = full_response[i:i+chunk_size]
                callback(chunk)
                # Petite pause pour simuler le streaming
                await asyncio.sleep(0.05)
            
        except Exception as e:
            error_msg = f"Erreur lors de la génération de texte en streaming: {str(e)}"
            logger.error(error_msg)
            # Envoyer l'erreur au client
            callback(f"[ERROR]: {error_msg}")
            raise
    
    def _convert_messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        """
        Convertit une liste de messages en un format de prompt texte.
        
        Args:
            messages: Liste de messages au format {"role": "...", "content": "..."}
            
        Returns:
            Prompt texte formaté
        """
        prompt = ""
        
        for message in messages:
            role = message.get("role", "").lower()
            content = message.get("content", "")
            
            if role == "system":
                prompt += f"Instructions: {content}\n\n"
            elif role == "user":
                prompt += f"Human: {content}\n"
            elif role == "assistant":
                prompt += f"AI: {content}\n"
            else:
                # Rôle inconnu, utiliser tel quel
                prompt += f"{role.capitalize()}: {content}\n"
        
        # Ajouter le préfixe final pour indiquer que c'est au tour de l'IA de répondre
        prompt += "AI: "
        
        return prompt 