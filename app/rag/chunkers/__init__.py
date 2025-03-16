from typing import Dict, Any
from app.schemas.document import ChunkingStrategy
from app.rag.chunkers.text_chunker import FixedSizeChunker
from app.rag.chunkers.semantic_chunker import SemanticChunker

# Mapping des stratégies de chunking
CHUNKER_MAPPING = {
    ChunkingStrategy.FIXED_SIZE: FixedSizeChunker,
    ChunkingStrategy.SEMANTIC: SemanticChunker,
    ChunkingStrategy.RECURSIVE: FixedSizeChunker,  # Utiliser FixedSizeChunker pour l'instant
    ChunkingStrategy.SENTENCE: FixedSizeChunker,   # Utiliser FixedSizeChunker pour l'instant
    ChunkingStrategy.PARAGRAPH: FixedSizeChunker,  # Utiliser FixedSizeChunker pour l'instant
}

async def get_chunker(strategy_name: str):
    """
    Récupérer le chunker approprié selon la stratégie spécifiée.
    """
    strategy = ChunkingStrategy(strategy_name) if strategy_name in ChunkingStrategy._value2member_map_ else ChunkingStrategy.FIXED_SIZE
    
    chunker_class = CHUNKER_MAPPING.get(strategy, FixedSizeChunker)
    return chunker_class()