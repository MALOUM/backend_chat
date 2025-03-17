"""
Module définissant l'interface de base pour les stores de vecteurs.
"""

import abc
import logging
from typing import List, Dict, Any, Optional, Union

from langchain.schema import Document
from app.ingestion_service.embedding.base_embedding import EmbeddingModel

logger = logging.getLogger(__name__)


class VectorStore(abc.ABC):
    """
    Classe abstraite définissant l'interface pour les stores de vecteurs.
    Les stores de vecteurs sont responsables de stocker et rechercher
    des embeddings vectoriels associés à des documents.
    """
    
    def __init__(self, embedding_model: EmbeddingModel, collection_name: str):
        """
        Initialise le store de vecteurs.
        
        Args:
            embedding_model: Modèle d'embedding à utiliser
            collection_name: Nom de la collection dans la base de données
        """
        self.embedding_model = embedding_model
        self.collection_name = collection_name
        logger.info(f"Initialisation du store de vecteurs {self.__class__.__name__}, "
                   f"collection: {collection_name}, modèle: {embedding_model.__class__.__name__}")
    
    @abc.abstractmethod
    async def add_documents(self, documents: List[Document]) -> Dict[str, Any]:
        """
        Ajoute des documents au store de vecteurs.
        
        Args:
            documents: Liste de documents à ajouter
            
        Returns:
            Dictionnaire contenant des informations sur l'opération
        """
        pass
    
    @abc.abstractmethod
    async def add_texts(self, texts: List[str], metadatas: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Ajoute des textes au store de vecteurs.
        
        Args:
            texts: Liste de textes à ajouter
            metadatas: Liste de métadonnées associées aux textes
            
        Returns:
            Dictionnaire contenant des informations sur l'opération
        """
        pass
    
    @abc.abstractmethod
    async def similarity_search(
        self,
        query: str,
        k: int = 4,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """
        Recherche les documents similaires à une requête.
        
        Args:
            query: Requête textuelle
            k: Nombre de résultats à renvoyer
            filter: Filtre supplémentaire pour la recherche
            
        Returns:
            Liste de documents similaires
        """
        pass
    
    @abc.abstractmethod
    async def similarity_search_by_vector(
        self,
        embedding: List[float],
        k: int = 4,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """
        Recherche les documents similaires à un vecteur d'embedding.
        
        Args:
            embedding: Vecteur d'embedding
            k: Nombre de résultats à renvoyer
            filter: Filtre supplémentaire pour la recherche
            
        Returns:
            Liste de documents similaires
        """
        pass
    
    @abc.abstractmethod
    async def delete(self, ids: Optional[List[str]] = None, filter: Optional[Dict[str, Any]] = None) -> None:
        """
        Supprime des documents du store de vecteurs.
        
        Args:
            ids: Liste d'identifiants de documents à supprimer
            filter: Filtre pour sélectionner les documents à supprimer
        """
        pass
    
    @abc.abstractmethod
    async def get_collection_stats(self) -> Dict[str, Any]:
        """
        Renvoie des statistiques sur la collection.
        
        Returns:
            Dictionnaire contenant les statistiques
        """
        pass
    
    @property
    @abc.abstractmethod
    def is_empty(self) -> bool:
        """
        Vérifie si le store de vecteurs est vide.
        
        Returns:
            True si le store est vide, False sinon
        """
        pass 