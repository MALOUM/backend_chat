from typing import List, Dict, Any
import logging
import numpy as np

from app.rag.retrievers.embedding import EmbeddingRetriever
from app.rag.retrievers.bm25 import BM25Retriever
from app import config

logger = logging.getLogger(__name__)

class HybridRetriever:
    """Retriever hybride combinant recherche sémantique et mots-clés."""
    
    def __init__(self):
        self.embedding_retriever = EmbeddingRetriever()
        self.bm25_retriever = BM25Retriever()
    
    async def retrieve(
        self,
        query: str,
        user_id: str,
        top_k: int = None,
        semantic_weight: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Récupérer les documents pertinents en combinant recherche sémantique et par mots-clés.
        semantic_weight: poids accordé à la recherche sémantique (vs mots-clés)
        """
        if top_k is None:
            top_k = config.TOP_K_RETRIEVAL
            
        try:
            # Augmenter le nombre de résultats à récupérer pour chaque méthode
            retrieval_k = min(top_k * 2, 20)
            
            # Récupérer les résultats de chaque méthode
            semantic_results = await self.embedding_retriever.retrieve(query, user_id, retrieval_k)
            keyword_results = await self.bm25_retriever.retrieve(query, user_id, retrieval_k)
            
            # Combiner les résultats
            combined_results = {}
            
            # Ajouter les résultats sémantiques
            for result in semantic_results:
                doc_id = result["document_id"]
                combined_results[doc_id] = {
                    **result,
                    "semantic_score": result["score"],
                    "keyword_score": 0.0,
                    "combined_score": semantic_weight * result["score"]
                }
            
            # Ajouter/mettre à jour avec les résultats par mots-clés
            for result in keyword_results:
                doc_id = result["document_id"]
                
                if doc_id in combined_results:
                    # Mettre à jour un document existant
                    combined_results[doc_id]["keyword_score"] = result["score"]
                    combined_results[doc_id]["combined_score"] += (1 - semantic_weight) * result["score"]
                else:
                    # Ajouter un nouveau document
                    combined_results[doc_id] = {
                        **result,
                        "semantic_score": 0.0,
                        "keyword_score": result["score"],
                        "combined_score": (1 - semantic_weight) * result["score"]
                    }
            
            # Trier par score combiné et limiter au top_k
            sorted_results = sorted(
                combined_results.values(),
                key=lambda x: x["combined_score"],
                reverse=True
            )[:top_k]
            
            # Normaliser les scores pour la réponse finale
            for result in sorted_results:
                result["score"] = result["combined_score"]
                del result["combined_score"]
            
            return sorted_results
        except Exception as e:
            logger.error(f"Erreur lors de la récupération hybride: {e}")
            return []