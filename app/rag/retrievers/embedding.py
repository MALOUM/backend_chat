from typing import List, Dict, Any
import logging
from sentence_transformers import SentenceTransformer

from app.db.mongodb import get_document_collection
from app.db.milvus import search_similar_documents
from app import config

logger = logging.getLogger(__name__)

class EmbeddingRetriever:
    """Retriever basé sur les embeddings."""
    
    def __init__(self):
        self.model = None
    
    async def _load_model(self):
        """Charger le modèle d'embeddings."""
        if not self.model:
            self.model = SentenceTransformer(config.EMBEDDING_MODEL)
    
    async def retrieve(
        self,
        query: str,
        user_id: str,
        top_k: int = None
    ) -> List[Dict[str, Any]]:
        """
        Récupérer les documents pertinents pour une requête.
        """
        if top_k is None:
            top_k = config.TOP_K_RETRIEVAL
            
        try:
            # Charger le modèle
            await self._load_model()
            
            # Générer l'embedding de la requête
            query_embedding = self.model.encode(query)
            
            # Rechercher dans Milvus
            search_results = await search_similar_documents(query_embedding, limit=top_k)
            
            # Formater les résultats
            document_collection = await get_document_collection()
            results = []
            
            if search_results and search_results[0]:
                for hit in search_results[0]:
                    document_id = hit.entity.get('document_id')
                    chunk_id = hit.entity.get('chunk_id')
                    content = hit.entity.get('content')
                    
                    # Récupérer les métadonnées du document
                    document = await document_collection.find_one({"_id": document_id})
                    
                    if document and document.get("user_id") == user_id:
                        results.append({
                            "document_id": document_id,
                            "document_title": document.get("title", ""),
                            "chunk_id": chunk_id,
                            "content": content,
                            "score": hit.score,
                            "metadata": document.get("metadata", {})
                        })
            
            return results
        except Exception as e:
            logger.error(f"Erreur lors de la récupération par embeddings: {e}")
            return []

    async def generate_embedding(self, text: str) -> List[float]:
        """
        Générer l'embedding d'un texte.
        """
        await self._load_model()
        return self.model.encode(text).tolist()