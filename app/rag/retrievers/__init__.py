from typing import Dict, Any
from app.schemas.chat import RAGStrategyEnum
from app.rag.retrievers.embedding import EmbeddingRetriever
from app.rag.retrievers.bm25 import BM25Retriever
from app.rag.retrievers.hybrid import HybridRetriever

# Mapping des stratégies de retrieval
RETRIEVER_MAPPING = {
    RAGStrategyEnum.BASIC: EmbeddingRetriever,
    RAGStrategyEnum.HYBRID_SEARCH: HybridRetriever,
    RAGStrategyEnum.RERANKING: EmbeddingRetriever,  # La phase de reranking est gérée ailleurs
    RAGStrategyEnum.SEMANTIC_CHUNKING: EmbeddingRetriever,
    RAGStrategyEnum.RECURSIVE: EmbeddingRetriever,
}

async def get_retriever(strategy_name: str):
    """
    Récupérer le retriever approprié selon la stratégie spécifiée.
    """
    strategy = RAGStrategyEnum(strategy_name) if strategy_name in RAGStrategyEnum._value2member_map_ else RAGStrategyEnum.BASIC
    
    retriever_class = RETRIEVER_MAPPING.get(strategy, EmbeddingRetriever)
    return retriever_class()