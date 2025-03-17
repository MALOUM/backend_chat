"""
Module définissant l'interface de base pour les chunkers de documents.
"""

import abc
import logging
from typing import List, Dict, Any, Optional

from langchain.schema import Document

logger = logging.getLogger(__name__)


class DocumentChunker(abc.ABC):
    """
    Classe abstraite définissant l'interface pour les chunkers de documents.
    Les chunkers sont responsables de diviser les documents en morceaux (chunks)
    plus petits pour un traitement et une recherche efficaces.
    """
    
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        """
        Initialise le chunker avec les paramètres de base.
        
        Args:
            chunk_size: Taille cible des chunks en nombre de caractères ou tokens
            chunk_overlap: Chevauchement entre les chunks consécutifs
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        logger.info(f"Initialisation du chunker {self.__class__.__name__} avec "
                   f"taille={chunk_size}, chevauchement={chunk_overlap}")
    
    @abc.abstractmethod
    async def split(self, documents: List[Document]) -> List[Document]:
        """
        Divise une liste de documents en chunks.
        
        Args:
            documents: Liste de documents à découper
            
        Returns:
            Liste de chunks (documents plus petits)
        """
        pass
    
    def _validate_parameters(self):
        """
        Valide les paramètres du chunker.
        
        Raises:
            ValueError: Si les paramètres sont invalides
        """
        if self.chunk_size <= 0:
            raise ValueError(f"La taille du chunk doit être positive, reçu: {self.chunk_size}")
        
        if self.chunk_overlap < 0:
            raise ValueError(f"Le chevauchement ne peut pas être négatif, reçu: {self.chunk_overlap}")
        
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError(f"Le chevauchement ({self.chunk_overlap}) doit être inférieur à la taille du chunk ({self.chunk_size})")
    
    def _merge_metadata(self, original_metadata: Dict[str, Any], chunk_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fusionne les métadonnées originales du document avec les métadonnées du chunk.
        
        Args:
            original_metadata: Métadonnées du document original
            chunk_metadata: Métadonnées spécifiques au chunk
            
        Returns:
            Métadonnées fusionnées
        """
        merged = original_metadata.copy() if original_metadata else {}
        if chunk_metadata:
            merged.update(chunk_metadata)
        return merged 