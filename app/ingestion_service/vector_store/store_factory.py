"""
Module de factory pour les stores de vecteurs.
"""

import logging
from typing import Dict, Any, Optional, List, Union

from app.ingestion_service.embedding.base_embedding import EmbeddingModel
from app.ingestion_service.vector_store.base_store import VectorStore
from app.ingestion_service.vector_store.milvus_store import MilvusStore

logger = logging.getLogger(__name__)


class VectorStoreFactory:
    """
    Factory pour créer différents types de stores de vecteurs.
    """
    
    TYPES = {
        "milvus": MilvusStore,
        # Ajoutez d'autres types de stores ici si nécessaire
    }
    
    @classmethod
    async def create_vector_store(
        cls,
        store_type: str,
        embedding_model: EmbeddingModel,
        collection_name: str,
        **kwargs
    ) -> VectorStore:
        """
        Crée un store de vecteurs en fonction du type spécifié.
        
        Args:
            store_type: Type de store de vecteurs ("milvus", etc.)
            embedding_model: Modèle d'embedding à utiliser
            collection_name: Nom de la collection
            **kwargs: Arguments supplémentaires spécifiques au type de store
            
        Returns:
            Instance du store de vecteurs
            
        Raises:
            ValueError: Si le type de store n'est pas pris en charge
        """
        if store_type.lower() not in cls.TYPES:
            supported = ", ".join(cls.TYPES.keys())
            raise ValueError(f"Type de store non pris en charge: {store_type}. Types pris en charge: {supported}")
        
        store_class = cls.TYPES[store_type.lower()]
        logger.info(f"Création d'un store de vecteurs de type {store_type}")
        
        # Créer l'instance du store
        store = store_class(embedding_model=embedding_model, collection_name=collection_name, **kwargs)
        
        return store
    
    @classmethod
    def get_available_types(cls) -> List[str]:
        """
        Renvoie la liste des types de stores disponibles.
        
        Returns:
            Liste des types de stores disponibles
        """
        return list(cls.TYPES.keys())
    
    @classmethod
    def get_store_info(cls, store_type: str) -> Dict[str, Any]:
        """
        Renvoie des informations sur un type de store spécifique.
        
        Args:
            store_type: Type de store
            
        Returns:
            Dictionnaire d'informations sur le store
            
        Raises:
            ValueError: Si le type de store n'est pas pris en charge
        """
        if store_type.lower() not in cls.TYPES:
            supported = ", ".join(cls.TYPES.keys())
            raise ValueError(f"Type de store non pris en charge: {store_type}. Types pris en charge: {supported}")
        
        store_class = cls.TYPES[store_type.lower()]
        
        store_info = {
            "type": store_type,
            "class": store_class.__name__,
            "description": store_class.__doc__.strip() if store_class.__doc__ else "Pas de description disponible"
        }
        
        return store_info 