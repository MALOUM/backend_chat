"""
Factory pour la création de chunkers de documents.
"""

import logging
from typing import Dict, Type, Optional

from app.ingestion_service.chunker.base_chunker import DocumentChunker
from app.ingestion_service.chunker.recursive_chunker import RecursiveChunker
from app.ingestion_service.chunker.fixed_size_chunker import FixedSizeChunker
from app.ingestion_service.chunker.semantic_chunker import SemanticChunker

logger = logging.getLogger(__name__)


class ChunkerFactory:
    """
    Factory pour créer différents types de chunkers de documents.
    Utilise le pattern Factory pour instancier le bon type de chunker en fonction
    de la stratégie de découpage demandée.
    """
    
    def __init__(self):
        """
        Initialise la factory avec le mapping des types de chunkers vers les classes.
        """
        self._chunker_map: Dict[str, Type[DocumentChunker]] = {
            "recursive": RecursiveChunker,
            "fixed": FixedSizeChunker,
            "semantic": SemanticChunker
        }
    
    def create_chunker(
        self,
        chunking_strategy: str,
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ) -> DocumentChunker:
        """
        Crée un chunker approprié pour la stratégie demandée.
        
        Args:
            chunking_strategy: Stratégie de découpage ("recursive", "fixed", "semantic")
            chunk_size: Taille des chunks
            chunk_overlap: Chevauchement entre les chunks
            
        Returns:
            Une instance de DocumentChunker appropriée
            
        Raises:
            ValueError: Si la stratégie de découpage n'est pas prise en charge
        """
        chunking_strategy = chunking_strategy.lower()
        
        if chunking_strategy not in self._chunker_map:
            available_strategies = ", ".join(self._chunker_map.keys())
            raise ValueError(f"Stratégie de découpage non prise en charge: {chunking_strategy}. "
                            f"Stratégies disponibles: {available_strategies}")
        
        chunker_class = self._chunker_map[chunking_strategy]
        logger.info(f"Création d'un chunker de type {chunker_class.__name__} "
                   f"avec taille={chunk_size}, chevauchement={chunk_overlap}")
        
        return chunker_class(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    
    def register_chunker(self, strategy_name: str, chunker_class: Type[DocumentChunker]) -> None:
        """
        Enregistre un nouveau type de chunker dans la factory.
        
        Args:
            strategy_name: Nom de la stratégie de découpage
            chunker_class: Classe de chunker
        """
        self._chunker_map[strategy_name.lower()] = chunker_class
        logger.info(f"Chunker {chunker_class.__name__} enregistré pour la stratégie {strategy_name}")
    
    def get_available_strategies(self) -> list:
        """
        Renvoie la liste des stratégies de découpage prises en charge.
        
        Returns:
            Liste des stratégies de découpage prises en charge
        """
        return list(self._chunker_map.keys()) 