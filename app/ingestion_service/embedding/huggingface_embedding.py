"""
Module implémentant un modèle d'embedding via HuggingFace.
"""

import os
import logging
import asyncio
from typing import List, Dict, Any, Optional, Union
import numpy as np

from app.ingestion_service.embedding.base_embedding import EmbeddingModel
from app import config

logger = logging.getLogger(__name__)


class HuggingFaceEmbedding(EmbeddingModel):
    """
    Modèle d'embedding utilisant les modèles de HuggingFace.
    
    Cette classe utilise des modèles pré-entraînés de HuggingFace pour 
    générer des embeddings vectoriels, en particulier les modèles de 
    Sentence Transformers.
    """
    
    # Caractéristiques des modèles populaires
    MODELS = {
        "sentence-transformers/all-MiniLM-L6-v2": {
            "dimension": 384,
            "description": "Modèle léger et rapide, bon équilibre performance/vitesse",
            "type": "sentence-transformer"
        },
        "sentence-transformers/all-mpnet-base-v2": {
            "dimension": 768,
            "description": "Haute qualité, plus lent mais plus précis",
            "type": "sentence-transformer"
        },
        "sentence-transformers/multi-qa-mpnet-base-dot-v1": {
            "dimension": 768,
            "description": "Optimisé pour la recherche de questions/réponses",
            "type": "sentence-transformer"
        },
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2": {
            "dimension": 384,
            "description": "Modèle multilingue",
            "type": "sentence-transformer"
        },
        "intfloat/e5-small-v2": {
            "dimension": 384,
            "description": "Nouvelle génération E5, bon rapport performance/taille",
            "type": "sentence-transformer"
        },
        "intfloat/e5-base-v2": {
            "dimension": 768,
            "description": "Nouvelle génération E5, haute performance",
            "type": "sentence-transformer"
        }
    }
    
    def __init__(self, model_name: Optional[str] = None):
        """
        Initialise le modèle d'embedding HuggingFace.
        
        Args:
            model_name: Nom du modèle HuggingFace à utiliser
        """
        model_name = model_name or config.EMBEDDING_MODEL or "sentence-transformers/all-MiniLM-L6-v2"
        super().__init__(model_name)
        
        self._model = None
        self._model_info = self.MODELS.get(model_name, {
            "dimension": config.EMBEDDING_DIMENSION or 384,
            "description": "Modèle personnalisé",
            "type": "custom"
        })
    
    @property
    def model(self):
        """
        Accède au modèle en le chargeant à la demande (lazy loading).
        
        Returns:
            Le modèle HuggingFace instancié
        """
        if self._model is None:
            try:
                logger.info(f"Chargement du modèle HuggingFace: {self.model_name}")
                
                # Importer ici pour éviter de charger les dépendances au démarrage
                from sentence_transformers import SentenceTransformer
                
                self._model = SentenceTransformer(self.model_name)
                logger.info(f"Modèle HuggingFace chargé avec succès: {self.model_name}")
            except Exception as e:
                logger.error(f"Erreur lors du chargement du modèle HuggingFace {self.model_name}: {str(e)}")
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
            
            return embedding.tolist()
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération d'embedding HuggingFace: {str(e)}")
            raise
    
    def _embed_query_sync(self, text: str) -> np.ndarray:
        """
        Version synchrone de embed_query.
        
        Args:
            text: Texte à transformer en embedding
            
        Returns:
            Vecteur d'embedding (numpy array)
        """
        return self.model.encode(text, normalize_embeddings=True)
    
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
            logger.info(f"Génération d'embeddings pour {len(texts)} documents")
            
            # Utiliser un thread pour l'exécution synchrone du modèle
            embeddings = await asyncio.to_thread(self._embed_documents_sync, texts)
            
            # Conversion des numpy arrays en listes Python
            embeddings_list = [embedding.tolist() for embedding in embeddings]
            
            logger.debug(f"Embeddings générés avec succès, dimension: {len(embeddings_list[0])}")
            return embeddings_list
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération d'embeddings HuggingFace: {str(e)}")
            raise
    
    def _embed_documents_sync(self, texts: List[str]) -> np.ndarray:
        """
        Version synchrone de embed_documents.
        
        Args:
            texts: Liste de textes à transformer en embeddings
            
        Returns:
            Liste de vecteurs d'embedding (numpy arrays)
        """
        return self.model.encode(texts, normalize_embeddings=True)
    
    def get_metadata(self) -> Dict[str, Any]:
        """
        Renvoie les métadonnées du modèle d'embedding.
        
        Returns:
            Dictionnaire contenant les métadonnées du modèle
        """
        return {
            "model_name": self.model_name,
            "model_provider": "huggingface",
            "dimension": self.dimension,
            "description": self._model_info.get("description", ""),
            "type": self._model_info.get("type", "custom")
        } 