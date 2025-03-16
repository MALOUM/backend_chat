from typing import Dict, Any
from app.schemas.chat import RAGStrategyEnum
from app.rag.rerankers.cross_encoder import CrossEncoderReranker

# Mapping des stratégies de reranking
RERANKER_MAPPING = {
    RAGStrategyEnum.RERANKING: CrossEncoderReranker,
}

async def get_reranker(strategy_name: str):
    """
    Récupérer le reranker approprié selon la stratégie spécifiée.
    """
    strategy = RAGStrategyEnum(strategy_name) if strategy_name in RAGStrategyEnum._value2member_map_ else None
    
    if strategy in RERANKER_MAPPING:
        reranker_class = RERANKER_MAPPING[strategy]
        return reranker_class()
    
    return None  # Pas de reranking pour cette stratégie