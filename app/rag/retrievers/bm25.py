from typing import List, Dict, Any
import logging
import re
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from rank_bm25 import BM25Okapi

from app.db.mongodb import get_document_collection
from app import config

logger = logging.getLogger(__name__)

class BM25Retriever:
    """Retriever basé sur BM25 (recherche par mots-clés)."""
    
    def __init__(self):
        self.tokenizer = None
    
    def _tokenize(self, text: str) -> List[str]:
        """Tokenizer simple pour BM25."""
        text = text.lower()
        # Supprimer la ponctuation et diviser en mots
        tokens = re.findall(r'\b\w+\b', text)
        return tokens
    
    async def retrieve(
        self,
        query: str,
        user_id: str,
        top_k: int = None
    ) -> List[Dict[str, Any]]:
        """
        Récupérer les documents pertinents pour une requête en utilisant BM25.
        """
        if top_k is None:
            top_k = config.TOP_K_RETRIEVAL
            
        try:
            # Récupérer tous les documents de l'utilisateur
            document_collection = await get_document_collection()
            documents = []
            
            cursor = document_collection.find({"user_id": user_id})
            async for doc in cursor:
                documents.append({
                    "id": doc["_id"],
                    "title": doc["title"],
                    "content": doc["content"],
                    "metadata": doc["metadata"]
                })
            
            if not documents:
                return []
            
            # Préparer les corpus et les identifiants
            corpus = [doc["content"] for doc in documents]
            doc_ids = [doc["id"] for doc in documents]
            
            # Tokenizer les documents et la requête
            tokenized_corpus = [self._tokenize(doc) for doc in corpus]
            tokenized_query = self._tokenize(query)
            
            # Créer et exécuter le modèle BM25
            bm25 = BM25Okapi(tokenized_corpus)
            scores = bm25.get_scores(tokenized_query)
            
            # Trier les résultats par score
            results_idx = np.argsort(scores)[::-1][:top_k]
            
            # Formater les résultats
            results = []
            for idx in results_idx:
                if scores[idx] > 0:  # Ignorer les scores nuls
                    results.append({
                        "document_id": doc_ids[idx],
                        "document_title": documents[idx]["title"],
                        "content": corpus[idx],
                        "score": float(scores[idx]),
                        "metadata": documents[idx]["metadata"]
                    })
            
            return results
        except Exception as e:
            logger.error(f"Erreur lors de la récupération par BM25: {e}")
            return []