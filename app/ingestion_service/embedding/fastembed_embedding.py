"""
Module implémentant un modèle d'embedding via FastEmbed.
"""

import os
import logging
import asyncio
from typing import List, Dict, Any, Optional, Union
import numpy as np

from app.ingestion_service.embedding.base_embedding import EmbeddingModel
from app import config

logger = logging.getLogger(__name__)


class FastEmbedEmbedding(EmbeddingModel):
    """
    Modèle d'embedding utilisant la bibliothèque FastEmbed.
    
    FastEmbed est une bibliothèque légère et rapide pour générer des embeddings
    avec des modèles optimisés qui fonctionnent localement sans API.
    """
    
    # Caractéristiques des modèles disponibles
    MODELS = {
        "gte-small": {
            "dimension": 384,
            "description": "Modèle GTE Small optimisé (< 100MB)",
            "size_mb": 90
        },
        "gte-base": {
            "dimension": 768,
            "description": "Modèle GTE Base (équilibré taille/qualité)",
            "size_mb": 220
        },
        "gte-large": {
            "dimension": 1024,
            "description": "Modèle GTE Large - haute qualité",
            "size_mb": 330
        },
        "bge-small": {
            "dimension": 384,
            "description": "Modèle BGE Small (optimisé pour le chinois et l'anglais)",
            "size_mb": 130
        },
        "bge-base": {
            "dimension": 768,
            "description": "Modèle BGE Base (optimisé pour le chinois et l'anglais)",
            "size_mb": 240
        },
        "e5-small": {
            "dimension": 384,
            "description": "Modèle E5 Small",
            "size_mb": 90
        }
    }
    
    def __init__(self, model_name: Optional[str] = None, cache_dir: Optional[str] = None):
        """
        Initialise le modèle d'embedding FastEmbed.
        
        Args:
            model_name: Nom du modèle FastEmbed à utiliser (gte-small, gte-base, etc.)
            cache_dir: Répertoire de cache pour les modèles (optionnel)
        """
        model_name = model_name or "gte-small"
        if model_name not in self.MODELS:
            logger.warning(f"Modèle FastEmbed inconnu: {model_name}. Utilisation de gte-small")
            model_name = "gte-small"
            
        super().__init__(model_name)
        
        self.cache_dir = cache_dir
        self._model = None
        self._model_info = self.MODELS[model_name]
    
    @property
    def model(self):
        """
        Accède au modèle en le chargeant à la demande (lazy loading).
        
        Returns:
            Le modèle FastEmbed instancié
        """
        if self._model is None:
            try:
                logger.info(f"Chargement du modèle FastEmbed: {self.model_name}")
                
                # Importer ici pour éviter de charger les dépendances au démarrage
                from fastembed import TextEmbedding
                
                # Définir le répertoire de cache si spécifié
                kwargs = {}
                if self.cache_dir:
                    kwargs["cache_dir"] = self.cache_dir
                
                self._model = TextEmbedding(self.model_name, **kwargs)
                logger.info(f"Modèle FastEmbed chargé avec succès: {self.model_name}")
            except Exception as e:
                logger.error(f"Erreur lors du chargement du modèle FastEmbed {self.model_name}: {str(e)}")
                raise
        return self._model
    
    @property
    def dimension(self) -> int:
        """
        Dimension de l'embedding pour le modèle actuel.
        
        Returns:
            Dimension de l'embedding
        """
        return self._model_info["dimension"]
    
    async def embed_query(self, text: str) -> List[float]:
        """
        Génère un embedding pour une requête (texte unique).
        
        Args:
            text: Texte à transformer en embedding
            
        Returns:
            Vecteur d'embedding
            
        Raises:
            ValueError: Si le texte est vide
        """
        self._validate_text(text)
        
        try:
            logger.debug(f"Génération d'un embedding pour une requête de {len(text)} caractères")
            
            # Utiliser un thread pour l'exécution synchrone du modèle
            embedding = await asyncio.to_thread(self._embed_query_sync, text)
            
            return embedding
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération d'embedding FastEmbed: {str(e)}")
            raise
    
    def _embed_query_sync(self, text: str) -> List[float]:
        """
        Version synchrone de embed_query.
        
        Args:
            text: Texte à transformer en embedding
            
        Returns:
            Vecteur d'embedding
        """
        # FastEmbed renvoie un générateur, nous prenons le premier élément
        embedding = next(self.model.embed([text]))
        return embedding.tolist()
    
    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Génère des embeddings pour une liste de documents.
        
        Args:
            texts: Liste de textes à transformer en embeddings
            
        Returns:
            Liste de vecteurs d'embedding
            
        Raises:
            ValueError: Si la liste est vide ou contient des textes vides
        """
        self._validate_text(texts)
        
        try:
            logger.info(f"Génération d'embeddings pour {len(texts)} documents avec FastEmbed")
            
            # Utiliser un thread pour l'exécution synchrone du modèle
            embeddings = await asyncio.to_thread(self._embed_documents_sync, texts)
            
            logger.debug(f"Embeddings générés avec succès, dimension: {len(embeddings[0])}")
            return embeddings
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération d'embeddings FastEmbed: {str(e)}")
            raise
    
    def _embed_documents_sync(self, texts: List[str]) -> List[List[float]]:
        """
        Version synchrone de embed_documents.
        
        Args:
            texts: Liste de textes à transformer en embeddings
            
        Returns:
            Liste de vecteurs d'embedding
        """
        # FastEmbed renvoie un générateur
        embeddings = list(self.model.embed(texts))
        return [embedding.tolist() for embedding in embeddings]
    
    def get_metadata(self) -> Dict[str, Any]:
        """
        Renvoie les métadonnées du modèle d'embedding.
        
        Returns:
            Dictionnaire contenant les métadonnées du modèle
        """
        return {
            "model_name": self.model_name,
            "model_provider": "fastembed",
            "dimension": self.dimension,
            "description": self._model_info.get("description", ""),
            "size_mb": self._model_info.get("size_mb", 0),
            "is_local": True
        } 