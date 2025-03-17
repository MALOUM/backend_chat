"""
Module implémentant un modèle d'embedding via l'API OpenAI ou un serveur local compatible.
"""

import os
import logging
import asyncio
from typing import List, Dict, Any, Optional

import openai
from openai import AsyncOpenAI, OpenAI

from app.ingestion_service.embedding.base_embedding import EmbeddingModel
from app import config

logger = logging.getLogger(__name__)


class OpenAIEmbedding(EmbeddingModel):
    """
    Modèle d'embedding utilisant l'API OpenAI ou un serveur local compatible.
    
    Ce modèle peut générer des embeddings via:
    1. L'API OpenAI standard avec les modèles text-embedding-ada-002 ou text-embedding-3-small/large
    2. Un serveur local compatible avec l'API OpenAI (comme LM Studio) avec des modèles locaux
    """
    
    # Caractéristiques des modèles disponibles
    MODELS = {
        "text-embedding-ada-002": {
            "dimension": 1536,
            "price_per_1k_tokens": 0.0001,
            "max_tokens": 8191,
            "type": "openai"
        },
        "text-embedding-3-small": {
            "dimension": 1536,
            "price_per_1k_tokens": 0.00002,
            "max_tokens": 8191,
            "type": "openai"
        },
        "text-embedding-3-large": {
            "dimension": 3072,
            "price_per_1k_tokens": 0.00013,
            "max_tokens": 8191,
            "type": "openai"
        },
        "second-state/All-MiniLM-L6-v2-Embedding-GGUF": {
            "dimension": 384,
            "price_per_1k_tokens": 0,
            "max_tokens": 8191,
            "type": "local"
        }
    }
    
    def __init__(self, model_name: Optional[str] = None, api_key: Optional[str] = None, base_url: Optional[str] = None):
        """
        Initialise le modèle d'embedding OpenAI ou compatible.
        
        Args:
            model_name: Nom du modèle à utiliser
            api_key: Clé API (prend la clé API de config par défaut)
            base_url: URL de base pour l'API (pour les serveurs locaux)
        """
        # Utiliser le modèle local par défaut
        model_name = model_name or "second-state/All-MiniLM-L6-v2-Embedding-GGUF"
        
        # Si le modèle n'est pas dans la liste, l'ajouter avec des valeurs par défaut
        if model_name not in self.MODELS:
            logger.warning(f"Modèle inconnu: {model_name}. Ajout avec des valeurs par défaut.")
            self.MODELS[model_name] = {
                "dimension": 384,  # Dimension par défaut
                "price_per_1k_tokens": 0,
                "max_tokens": 8191,
                "type": "local" if "second-state" in model_name else "unknown"
            }
            
        super().__init__(model_name)
        
        # Déterminer si nous utilisons l'API OpenAI ou un serveur local
        model_type = self.MODELS[model_name]["type"]
        
        if model_type == "local":
            # Configuration pour un serveur local (LM Studio)
            self.api_key = api_key or "lm-studio"
            self.base_url = base_url or "http://localhost:1234/v1"
            logger.info(f"Utilisation d'un serveur d'embedding local: {self.base_url}")
        else:
            # Configuration pour l'API OpenAI standard
            self.api_key = api_key or config.OPENAI_API_KEY or os.environ.get("OPENAI_API_KEY")
            self.base_url = None
            
            if not self.api_key and model_type == "openai":
                raise ValueError("Clé API OpenAI non fournie et non trouvée dans les variables d'environnement")
        
        # Créer les clients OpenAI (synchrone et asynchrone)
        if self.base_url:
            self.async_client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        else:
            self.async_client = AsyncOpenAI(api_key=self.api_key)
            self.client = OpenAI(api_key=self.api_key)
    
    @property
    def dimension(self) -> int:
        """
        Dimension de l'embedding pour le modèle actuel.
        
        Returns:
            Dimension de l'embedding
        """
        return self.MODELS[self.model_name]["dimension"]
    
    async def embed_query(self, text: str) -> List[float]:
        """
        Génère un embedding pour une requête (texte unique).
        
        Args:
            text: Texte à transformer en embedding
            
        Returns:
            Vecteur d'embedding
            
        Raises:
            ValueError: Si le texte est vide
            Exception: Pour les erreurs d'API
        """
        self._validate_text(text)
        
        try:
            logger.debug(f"Génération d'un embedding pour une requête de {len(text)} caractères")
            
            # Remplacer les sauts de ligne par des espaces pour améliorer la qualité
            text = text.replace("\n", " ")
            
            response = await self.async_client.embeddings.create(
                model=self.model_name,
                input=text
            )
            
            return response.data[0].embedding
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération d'embedding: {str(e)}")
            raise
    
    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Génère des embeddings pour une liste de documents.
        
        Args:
            texts: Liste de textes à transformer en embeddings
            
        Returns:
            Liste de vecteurs d'embedding
            
        Raises:
            ValueError: Si la liste est vide ou contient des textes vides
            Exception: Pour les erreurs d'API
        """
        self._validate_text(texts)
        
        try:
            logger.info(f"Génération d'embeddings pour {len(texts)} documents")
            
            # Remplacer les sauts de ligne par des espaces pour améliorer la qualité
            processed_texts = [text.replace("\n", " ") for text in texts]
            
            # Appel à l'API
            response = await self.async_client.embeddings.create(
                model=self.model_name,
                input=processed_texts
            )
            
            # Extraire les embeddings de la réponse
            embeddings = [data.embedding for data in response.data]
            
            logger.debug(f"Embeddings générés avec succès, dimension: {len(embeddings[0])}")
            return embeddings
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération d'embeddings: {str(e)}")
            raise
    
    def get_metadata(self) -> Dict[str, Any]:
        """
        Renvoie les métadonnées du modèle d'embedding.
        
        Returns:
            Dictionnaire contenant les métadonnées du modèle
        """
        model_info = self.MODELS.get(self.model_name, {
            "dimension": 384,
            "max_tokens": 8191,
            "price_per_1k_tokens": 0,
            "type": "unknown"
        })
        
        return {
            "model_name": self.model_name,
            "model_provider": "local" if model_info["type"] == "local" else "openai",
            "dimension": self.dimension,
            "max_tokens": model_info["max_tokens"],
            "pricing": model_info["price_per_1k_tokens"],
            "type": model_info["type"],
            "base_url": self.base_url
        } 