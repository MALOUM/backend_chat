from typing import List, Dict, Any, Optional
import logging
import uuid

from app.schemas.chat import RAGStrategyEnum
from app.rag.chunkers import get_chunker
from app.rag.retrievers import get_retriever
from app.rag.rerankers import get_reranker
from app.rag.chunkers.text_chunker import TextChunk
from app.db.milvus import insert_embeddings
from app import config

logger = logging.getLogger(__name__)

class RAGPipeline:
    """Pipeline complet pour RAG."""
    
    def __init__(self, strategy: Optional[str] = None):
        self.strategy = strategy or RAGStrategyEnum.BASIC.value
        self.retriever = None
        self.reranker = None
    
    async def _initialize(self):
        """Initialiser les composants du pipeline."""
        if not self.retriever:
            self.retriever = await get_retriever(self.strategy)
        
        if not self.reranker:
            self.reranker = await get_reranker(self.strategy)
    
    async def retrieve(
        self,
        query: str,
        user_id: str,
        top_k: int = None
    ) -> List[Dict[str, Any]]:
        """
        Récupérer et reranker les documents pertinents.
        """
        await self._initialize()
        
        # Récupérer les documents
        results = await self.retriever.retrieve(query, user_id, top_k)
        
        # Reranker si nécessaire
        if self.reranker:
            results = await self.reranker.rerank(query, results, top_k)
        
        return results

async def get_rag_pipeline(strategy: Optional[str] = None) -> RAGPipeline:
    """
    Obtenir un pipeline RAG configuré pour la stratégie spécifiée.
    """
    return RAGPipeline(strategy)

async def embed_and_store(chunks: List[TextChunk], document_id: str) -> None:
    """
    Générer des embeddings pour des chunks et les stocker dans Milvus.
    """
    try:
        # Initialiser le retriever pour générer les embeddings
        retriever = await get_retriever(RAGStrategyEnum.BASIC.value)
        
        # Préparer les données pour Milvus
        embeddings_data = {
            "id": [],
            "document_id": [],
            "chunk_id": [],
            "content": [],
            "embedding": []
        }
        
        # Générer et collecter les embeddings
        for i, chunk in enumerate(chunks):
            chunk_id = f"{document_id}_chunk_{i}"
            embedding = await retriever.generate_embedding(chunk.text)
            
            embeddings_data["id"].append(chunk_id)
            embeddings_data["document_id"].append(document_id)
            embeddings_data["chunk_id"].append(chunk_id)
            embeddings_data["content"].append(chunk.text)
            embeddings_data["embedding"].append(embedding)
        
        # Insérer dans Milvus
        await insert_embeddings(embeddings_data)
        
        logger.info(f"Embeddings générés et stockés pour le document {document_id}")
    except Exception as e:
        logger.error(f"Erreur lors de la génération et du stockage des embeddings: {e}")
        raise