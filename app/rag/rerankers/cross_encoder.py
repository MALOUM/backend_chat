from typing import List, Dict, Any
import logging
import numpy as np
from sentence_transformers import CrossEncoder

logger = logging.getLogger(__name__)

class CrossEncoderReranker:
    """Reranker basé sur un Cross-Encoder."""
    
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model_name = model_name
        self.model = None
    
    async def _load_model(self):
        """Charger le modèle Cross-Encoder."""
        if not self.model:
            self.model = CrossEncoder(self.model_name)
    
    async def rerank(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: int = None
    ) -> List[Dict[str, Any]]:
        """
        Reranker les résultats de recherche en utilisant un Cross-Encoder.
        """
        if not results:
            return []
            
        if top_k is None:
            top_k = len(results)
            
        try:
            # Charger le modèle
            await self._load_model()
            
            # Préparer les paires (query, passage)
            pairs = [(query, result["content"]) for result in results]
            
            # Calculer les scores avec le Cross-Encoder
            scores = self.model.predict(pairs)
            
            # Trier les résultats par score
            for i, score in enumerate(scores):
                results[i]["original_score"] = results[i]["score"]
                results[i]["score"] = float(score)
            
            sorted_results = sorted(results, key=lambda x: x["score"], reverse=True)
            
            return sorted_results[:top_k]
        except Exception as e:
            logger.error(f"Erreur lors du reranking: {e}")
            return results  # Retourner les résultats originaux en cas d'erreur
