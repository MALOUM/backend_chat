"""
Module des chunkers de documents.

Ce module fournit des classes pour découper des documents en chunks:
- RecursiveChunker: Découpe récursivement en utilisant une hiérarchie de séparateurs
- FixedSizeChunker: Découpe en chunks de taille fixe
- SemanticChunker: Découpe en fonction du sens et de la cohérence sémantique

Les chunkers sont responsables de diviser les documents en morceaux plus petits
pour un traitement et une recherche plus efficaces.
"""

from app.ingestion_service.chunker.base_chunker import DocumentChunker
from app.ingestion_service.chunker.recursive_chunker import RecursiveChunker
from app.ingestion_service.chunker.fixed_size_chunker import FixedSizeChunker
from app.ingestion_service.chunker.semantic_chunker import SemanticChunker
from app.ingestion_service.chunker.factory import ChunkerFactory

__all__ = [
    'DocumentChunker',
    'RecursiveChunker',
    'FixedSizeChunker',
    'SemanticChunker',
    'ChunkerFactory'
] 