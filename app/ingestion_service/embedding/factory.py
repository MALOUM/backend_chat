"""
Factory pour la création de modèles d'embedding.
"""

import logging
from typing import Dict, Optional, Type, List, Any

from app.ingestion_service.embedding.base_embedding import EmbeddingModel
from app.ingestion_service.embedding.openai_embedding import OpenAIEmbedding
from app.ingestion_service.embedding.huggingface_embedding import HuggingFaceEmbedding
from app.ingestion_service.embedding.fastembed_embedding import FastEmbedEmbedding
from app import config

logger = logging.getLogger(__name__)


class EmbeddingFactory:
    """
    Factory pour créer différents types de modèles d'embedding.
    Utilise le pattern Factory pour instancier le bon type de modèle
    en fonction du fournisseur demandé.
    """
    
    def __init__(self):
        """
        Initialise la factory avec le mapping des types de modèles vers les classes.
        """
        self._embedding_map: Dict[str, Type[EmbeddingModel]] = {
            "openai": OpenAIEmbedding,
            "huggingface": HuggingFaceEmbedding,
            "fastembed": FastEmbedEmbedding
        }
    
    def create_embedding_model(
        self,
        embedding_type: str = "openai",
        model_name: Optional[str] = None
    ) -> EmbeddingModel:
        """
        Crée un modèle d'embedding approprié pour le type demandé.
        
        Args:
            embedding_type: Type de modèle d'embedding ("openai", "huggingface", "fastembed")
            model_name: Nom spécifique du modèle (optionnel)
            
        Returns:
            Une instance de EmbeddingModel appropriée
            
        Raises:
            ValueError: Si le type de modèle d'embedding n'est pas pris en charge
        """
        embedding_type = embedding_type.lower()
        
        if embedding_type not in self._embedding_map:
            available_types = ", ".join(self._embedding_map.keys())
            raise ValueError(f"Type de modèle d'embedding non pris en charge: {embedding_type}. "
                            f"Types disponibles: {available_types}")
        
        embedding_class = self._embedding_map[embedding_type]
        logger.info(f"Création d'un modèle d'embedding de type {embedding_class.__name__} "
                   f"avec modèle: {model_name or 'par défaut'}")
        
        # Créer l'instance avec les paramètres appropriés
        if embedding_type == "openai":
            # Pour OpenAI, utiliser par défaut le modèle local
            if model_name is None:
                model_name = "second-state/All-MiniLM-L6-v2-Embedding-GGUF"
                # Utiliser le serveur local LM Studio
                return embedding_class(
                    model_name=model_name,
                    api_key="lm-studio",
                    base_url="http://host.docker.internal:1234/v1"
                )
            else:
                # Si un modèle spécifique est demandé, vérifier s'il s'agit d'un modèle local
                if "second-state" in model_name or model_name.endswith("-GGUF"):
                    return embedding_class(
                        model_name=model_name,
                        api_key="lm-studio",
                        base_url="http://host.docker.internal:1234/v1"
                    )
                else:
                    # Sinon, utiliser l'API OpenAI standard
                    return embedding_class(
                        model_name=model_name,
                        api_key=config.OPENAI_API_KEY
                    )
        else:
            return embedding_class(model_name=model_name)
    
    def register_embedding_model(self, model_type: str, model_class: Type[EmbeddingModel]) -> None:
        """
        Enregistre un nouveau type de modèle d'embedding dans la factory.
        
        Args:
            model_type: Type de modèle d'embedding
            model_class: Classe du modèle d'embedding
        """
        self._embedding_map[model_type.lower()] = model_class
        logger.info(f"Modèle d'embedding {model_class.__name__} enregistré pour le type {model_type}")
    
    def get_available_models(self) -> Dict[str, Dict[str, Any]]:
        """
        Renvoie la liste des modèles d'embedding disponibles par type.
        
        Returns:
            Dictionnaire des types de modèles avec leurs modèles disponibles
        """
        available_models = {}
        
        # OpenAI
        available_models["openai"] = {
            "models": list(OpenAIEmbedding.MODELS.keys()),
            "default": "second-state/All-MiniLM-L6-v2-Embedding-GGUF",  # Modèle local par défaut
            "dimensions": {name: info["dimension"] for name, info in OpenAIEmbedding.MODELS.items()},
            "requires_api_key": False  # Pas besoin de clé API pour les modèles locaux
        }
        
        # HuggingFace
        available_models["huggingface"] = {
            "models": list(HuggingFaceEmbedding.MODELS.keys()),
            "default": "sentence-transformers/all-MiniLM-L6-v2",
            "dimensions": {name: info["dimension"] for name, info in HuggingFaceEmbedding.MODELS.items()},
            "requires_api_key": False
        }
        
        # FastEmbed
        available_models["fastembed"] = {
            "models": list(FastEmbedEmbedding.MODELS.keys()),
            "default": "gte-small",
            "dimensions": {name: info["dimension"] for name, info in FastEmbedEmbedding.MODELS.items()},
            "requires_api_key": False
        }
        
        return available_models
    
    def get_dimension(self, embedding_type: str, model_name: Optional[str] = None) -> int:
        """
        Renvoie la dimension des embeddings pour un type et un modèle donné.
        
        Args:
            embedding_type: Type de modèle d'embedding
            model_name: Nom du modèle (optionnel)
            
        Returns:
            Dimension des embeddings
            
        Raises:
            ValueError: Si le type ou le modèle n'est pas pris en charge
        """
        embedding_type = embedding_type.lower()
        
        if embedding_type not in self._embedding_map:
            available_types = ", ".join(self._embedding_map.keys())
            raise ValueError(f"Type de modèle d'embedding non pris en charge: {embedding_type}. "
                            f"Types disponibles: {available_types}")
        
        if embedding_type == "openai":
            model_name = model_name or "second-state/All-MiniLM-L6-v2-Embedding-GGUF"
            if model_name not in OpenAIEmbedding.MODELS:
                # Si le modèle n'est pas connu, supposer qu'il s'agit d'un modèle local avec dimension 384
                logger.warning(f"Modèle OpenAI inconnu: {model_name}, utilisation de la dimension par défaut (384)")
                return 384
            return OpenAIEmbedding.MODELS[model_name]["dimension"]
            
        elif embedding_type == "huggingface":
            model_name = model_name or "sentence-transformers/all-MiniLM-L6-v2"
            if model_name in HuggingFaceEmbedding.MODELS:
                return HuggingFaceEmbedding.MODELS[model_name]["dimension"]
            return config.EMBEDDING_DIMENSION or 384  # Valeur par défaut
            
        elif embedding_type == "fastembed":
            model_name = model_name or "gte-small"
            if model_name not in FastEmbedEmbedding.MODELS:
                raise ValueError(f"Modèle FastEmbed inconnu: {model_name}")
            return FastEmbedEmbedding.MODELS[model_name]["dimension"]
        
        # Ne devrait jamais arriver grâce à la vérification précédente
        raise ValueError(f"Type de modèle d'embedding non géré pour la dimension: {embedding_type}") 