"""
Module pour la gestion des stratégies RAG (Retrieval Augmented Generation) 
utilisant LangChain et LlamaIndex.

Ce module contient les stratégies de récupération de documents
pour augmenter les réponses générées par le modèle de langage.
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional, Union, Callable
import numpy as np
from datetime import datetime

# Imports LangChain
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import EmbeddingsFilter
from langchain_community.retrievers import MilvusRetriever
from langchain_community.vectorstores import Milvus
from langchain.schema import Document
from langchain.prompts.prompt import PromptTemplate
from langchain.output_parsers import PydanticOutputParser

# Imports LlamaIndex
from llama_index.core.retrievers import VectorIndexRetriever
# BM25Retriever est disponible dans llama_index.retrievers.bm25 après installation de llama-index-retrievers-bm25
from llama_index.retrievers.bm25 import BM25Retriever 
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.core.postprocessor import SimilarityPostprocessor


# Imports locaux
from app.db.mongodb import get_document_collection
from app.db import milvus as milvus_utils
from app.ingestion_service.embedding.factory import EmbeddingFactory
from app.schemas.chat import RAGStrategyEnum

logger = logging.getLogger(__name__)


class RAGStrategy:
    """Classe de base pour toutes les stratégies RAG."""
    
    def __init__(self, user_id: str):
        """
        Initialise la stratégie RAG.
        
        Args:
            user_id: ID de l'utilisateur pour filtrer les documents
        """
        self.user_id = user_id
        
        # Initialiser le modèle d'embedding (sera utilisé par toutes les stratégies)
        embedding_factory = EmbeddingFactory()
        self.embedding_model = embedding_factory.create_embedding_model("openai")
        
        # Utiliser la collection commune document_embeddings au lieu d'une collection par utilisateur
        self.collection_name = "document_embeddings"
    
    async def get_relevant_context(self, query: str, session_id: str = None) -> str:
        """
        Récupère les documents pertinents en utilisant une méthode directe avec Milvus.
        """
        try:
            logger.info(f"Récupération du contexte pour la requête: {query}")
            
            # Créer l'embedding pour la requête
            query_embedding = await self.embedding_model.embed_query(query)
            
            # Obtenir la collection Milvus directement
            collection = await milvus_utils.get_collection(self.collection_name)
            if not collection:
                logger.warning(f"Collection {self.collection_name} introuvable")
                return ""
            
            # Rechercher en utilisant l'API Milvus directement
            search_params = {"metric_type": "L2", "params": {"ef": 64}}
            results = collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=4,
                output_fields=["document_id", "chunk_id", "content"]
            )
            
            # Traiter les résultats
            documents = []
            if results and len(results) > 0:
                for hit in results[0]:
                    # Utiliser accesseur de manière sécurisée sans valeur par défaut
                    content = ""
                    document_id = ""
                    chunk_id = ""
                    
                    try:
                        content = hit.entity.get("content")
                    except:
                        pass
                        
                    try:
                        document_id = hit.entity.get("document_id")
                    except:
                        pass
                        
                    try:
                        chunk_id = hit.entity.get("chunk_id")
                    except:
                        pass
                    
                    documents.append({
                        "content": content or "",
                        "source": document_id or "",
                        "title": f"Extrait {chunk_id or ''}"
                    })
            
            # Formater le contexte
            context = self._format_context(documents)
            
            logger.info(f"Contexte récupéré: {len(documents)} documents")
            return context
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du contexte: {str(e)}")
            return ""
    
    def _format_context(self, documents: List[Union[Document, Dict[str, Any]]]) -> str:
        """
        Formate les documents récupérés en contexte pour le modèle de langage.
        
        Args:
            documents: Liste de documents ou chunks récupérés
            
        Returns:
            Contexte formaté
        """
        if not documents:
            return ""
        
        context = "Contexte:\n\n"
        
        for i, doc in enumerate(documents):
            # Gérer différents types de documents (LangChain Document ou dict)
            if isinstance(doc, Document):
                title = doc.metadata.get("title", f"Document {i+1}")
                content = doc.page_content
                source = doc.metadata.get("source", "")
            else:
                title = doc.get("title", f"Document {i+1}")
                content = doc.get("content", doc.get("page_content", ""))
                source = doc.get("source", "")
            
            context += f"--- {title} ---\n"
            context += content.strip() + "\n"
            if source:
                context += f"Source: {source}\n"
            context += "\n"
        
        return context
    


async def _get_langchain_retriever(self):
    """
    Crée un retriever LangChain pour Milvus compatible avec les versions récentes.
    
    Returns:
        Un retriever configuré pour l'utilisateur actuel
    """
    try:
        # Vérifier la connexion à Milvus
        connected = await milvus_utils.connect_to_milvus()
        if not connected:
            raise ConnectionError("Impossible de se connecter à Milvus")
        
        # Créer les arguments de connexion
        connection_args = {
            "host": "localhost",  # Utiliser "milvus" si dans Docker
            "port": "19530"
        }
        
        # Méthode 1: Utiliser le vectorstore Milvus directement
        vector_store = Milvus(
            embedding_function=self.embedding_model,
            collection_name=self.collection_name,
            connection_args=connection_args,
            text_key="content",
        )
        
        # Créer le retriever à partir du vectorstore
        retriever = vector_store.as_retriever(search_kwargs={"k": 4})
        return retriever
        
    except Exception as e:
        logger.error(f"Erreur lors de la création du retriever LangChain: {str(e)}")
        
        # Méthode alternative: utiliser MilvusRetriever directement
        try:
            logger.info("Tentative avec la méthode alternative MilvusRetriever...")
            retriever = MilvusRetriever(
                embedding_function=self.embedding_model,
                collection_name=self.collection_name,
                connection_args=connection_args,
                text_key="content",
                vector_key="embedding",  # Spécifier le nom du champ des vecteurs
                content_payload_key="content"  # Spécifier le nom du champ contenant le texte
            )
            return retriever
        except Exception as e2:
            logger.error(f"Échec de la méthode alternative: {str(e2)}")
            raise ValueError(f"Impossible de créer un retriever: {str(e)} / {str(e2)}")
    
    async def _get_documents_from_mongodb(self, filter_query: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
        """
        Récupère des documents depuis MongoDB avec un filtre spécifique.
        
        Args:
            filter_query: Filtre MongoDB
            limit: Nombre maximum de documents à récupérer
            
        Returns:
            Liste de documents
        """
        try:
            document_collection = await get_document_collection()
            
            # Ajouter le filtre utilisateur
            filter_query["user_id"] = self.user_id
            
            cursor = document_collection.find(filter_query).limit(limit)
            
            documents = []
            async for doc in cursor:
                # Convertir l'ID en chaîne de caractères
                doc["_id"] = str(doc["_id"])
                documents.append(doc)
            
            return documents
        except Exception as e:
            logger.error(f"Erreur lors de la récupération de documents depuis MongoDB: {str(e)}")
            return []


class BasicRAGStrategy(RAGStrategy):
    """
    Stratégie RAG basique qui utilise une recherche vectorielle directe avec Milvus.
    """
    
    async def get_relevant_context(self, query: str, session_id: str = None) -> str:
        """
        Récupère les documents les plus similaires à la requête en utilisant Milvus directement.
        
        Args:
            query: Requête de l'utilisateur
            session_id: ID de la session de chat (optionnel)
            
        Returns:
            Contexte formaté pour le modèle de langage
        """
        try:
            logger.info(f"Récupération du contexte avec BasicRAGStrategy pour: {query}")
            
            # 1. Vérifier la connexion à Milvus
            connected = await milvus_utils.connect_to_milvus()
            if not connected:
                logger.error("Impossible de se connecter à Milvus")
                return ""
            
            # 2. Générer l'embedding pour la requête
            query_embedding = await self.embedding_model.embed_query(query)
            
            # 3. Obtenir la collection Milvus
            collection = await milvus_utils.get_collection(self.collection_name)
            if not collection:
                logger.warning(f"Collection {self.collection_name} introuvable")
                return ""
            
            # 4. Effectuer la recherche de similarité
            search_params = {"metric_type": "L2", "params": {"ef": 64}}
            results = collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=4,  # Récupérer les 4 documents les plus similaires
                output_fields=["document_id", "chunk_id", "content"]
            )
            
            # 5. Traiter les résultats
            documents = []
            if results and len(results) > 0:
                for hit in results[0]:
                    # Récupérer les champs de manière sécurisée
                    content = ""
                    document_id = ""
                    chunk_id = ""
                    
                    try:
                        content = hit.entity.get("content")
                    except:
                        pass
                        
                    try:
                        document_id = hit.entity.get("document_id")
                    except:
                        pass
                        
                    try:
                        chunk_id = hit.entity.get("chunk_id")
                    except:
                        pass
                    
                    documents.append({
                        "content": content or "",
                        "source": document_id or "",
                        "title": f"Extrait {chunk_id or ''}"
                    })
            
            # 6. Formater le contexte
            context = self._format_context(documents)
            
            logger.info(f"Contexte récupéré avec BasicRAGStrategy: {len(documents)} documents")
            return context
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du contexte avec BasicRAGStrategy: {str(e)}")
            return ""

class HybridSearchRAGStrategy(RAGStrategy):
    """
    Stratégie RAG qui combine la recherche vectorielle et la recherche par mots-clés.
    """
    
    async def get_relevant_context(self, query: str, session_id: str = None) -> str:
        """
        Récupère les documents en utilisant une approche hybride.
        
        Args:
            query: Requête de l'utilisateur
            session_id: ID de la session de chat (optionnel)
            
        Returns:
            Contexte formaté pour le modèle de langage
        """
        try:
            logger.info(f"Récupération du contexte avec HybridSearchRAGStrategy pour: {query}")
            
            # 1. Partie recherche vectorielle
            # Vérifier la connexion à Milvus
            connected = await milvus_utils.connect_to_milvus()
            if not connected:
                logger.error("Impossible de se connecter à Milvus")
                return ""
            
            # Générer l'embedding pour la requête
            query_embedding = await self.embedding_model.embed_query(query)
            
            # Obtenir la collection Milvus
            collection = await milvus_utils.get_collection(self.collection_name)
            if not collection:
                logger.warning(f"Collection {self.collection_name} introuvable")
                return ""
            
            # Effectuer la recherche vectorielle
            search_params = {"metric_type": "L2", "params": {"ef": 64}}
            vector_results = collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=3,  # Récupérer 3 documents par recherche vectorielle
                output_fields=["document_id", "chunk_id", "content"]
            )
            
            # Traiter les résultats vectoriels
            vector_documents = []
            if vector_results and len(vector_results) > 0:
                for hit in vector_results[0]:
                    # Récupérer les champs de manière sécurisée
                    content = ""
                    document_id = ""
                    chunk_id = ""
                    
                    try:
                        content = hit.entity.get("content")
                    except:
                        pass
                        
                    try:
                        document_id = hit.entity.get("document_id")
                    except:
                        pass
                        
                    try:
                        chunk_id = hit.entity.get("chunk_id")
                    except:
                        pass
                    
                    vector_documents.append({
                        "content": content or "",
                        "source": document_id or "",
                        "title": f"Extrait {chunk_id or ''}"
                    })
            
            # 2. Partie recherche par mots-clés (MongoDB)
            document_collection = await get_document_collection()
            
            # Extraire les mots-clés de la requête
            keywords = [word for word in query.split() if len(word) > 3]
            text_search_results = []
            
            if keywords:
                text_query = " ".join(keywords)
                cursor = document_collection.find(
                    {
                        "$text": {"$search": text_query},
                        "user_id": self.user_id
                    },
                    {"score": {"$meta": "textScore"}}
                ).sort([("score", {"$meta": "textScore"})]).limit(2)
                
                async for doc in cursor:
                    text_search_results.append({
                        "content": doc.get("content", ""),
                        "source": str(doc.get("_id", "")),
                        "title": doc.get("title", "Document")
                    })
            
            # 3. Fusionner les résultats
            all_documents = vector_documents.copy()
            
            # Ajouter les résultats textuels s'ils ne sont pas déjà présents
            for text_doc in text_search_results:
                # Vérifier les doublons
                is_duplicate = False
                for vec_doc in vector_documents:
                    if text_doc["source"] == vec_doc["source"]:
                        is_duplicate = True
                        break
                
                if not is_duplicate:
                    all_documents.append(text_doc)
            
            # 4. Formater le contexte
            context = self._format_context(all_documents)
            
            logger.info(f"Contexte récupéré avec HybridSearchRAGStrategy: {len(all_documents)} documents")
            return context
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du contexte avec HybridSearchRAGStrategy: {str(e)}")
            return ""

class RerankingRAGStrategy(RAGStrategy):
    """
    Stratégie RAG qui réordonne les résultats récupérés en fonction
    de leur pertinence par rapport à la requête.
    """
    
    async def get_relevant_context(self, query: str, session_id: str = None) -> str:
        """
        Récupère et réordonne les documents pertinents.
        
        Args:
            query: Requête de l'utilisateur
            session_id: ID de la session de chat (optionnel)
            
        Returns:
            Contexte formaté pour le modèle de langage
        """
        try:
            logger.info(f"Récupération du contexte avec RerankingRAGStrategy pour: {query}")
            
            # 1. Vérifier la connexion à Milvus
            connected = await milvus_utils.connect_to_milvus()
            if not connected:
                logger.error("Impossible de se connecter à Milvus")
                return ""
            
            # 2. Générer l'embedding pour la requête
            query_embedding = await self.embedding_model.embed_query(query)
            
            # 3. Obtenir la collection Milvus
            collection = await milvus_utils.get_collection(self.collection_name)
            if not collection:
                logger.warning(f"Collection {self.collection_name} introuvable")
                return ""
            
            # 4. Récupérer un plus grand nombre de documents initiaux
            search_params = {"metric_type": "L2", "params": {"ef": 64}}
            results = collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=8,  # Récupérer plus de documents pour le reranking
                output_fields=["document_id", "chunk_id", "content"]
            )
            
            # 5. Traiter les résultats et préparer pour le reranking
            documents_for_reranking = []
            if results and len(results) > 0:
                for hit in results[0]:
                    # Récupérer les champs de manière sécurisée
                    content = ""
                    document_id = ""
                    chunk_id = ""
                    
                    try:
                        content = hit.entity.get("content")
                    except:
                        pass
                        
                    try:
                        document_id = hit.entity.get("document_id")
                    except:
                        pass
                        
                    try:
                        chunk_id = hit.entity.get("chunk_id")
                    except:
                        pass
                    
                    documents_for_reranking.append({
                        "content": content or "",
                        "source": document_id or "",
                        "title": f"Extrait {chunk_id or ''}",
                        "initial_score": hit.distance  # Score initial de similarité
                    })
            
            # 6. Reranking - Calculer un score plus précis pour chaque document
            ranked_documents = []
            for doc in documents_for_reranking:
                # Calculer un nouvel embedding pour le contenu du document
                # (pour une comparaison plus directe avec la requête)
                content_embedding = await self.embedding_model.embed_query(doc["content"])
                
                # Calculer la similarité cosinus entre la requête et le document
                similarity = self._cosine_similarity(query_embedding, content_embedding)
                
                # Combiner avec le score initial pour un classement plus robuste
                final_score = (similarity * 0.7) + ((1.0 - doc["initial_score"]) * 0.3)
                
                ranked_documents.append({
                    "content": doc["content"],
                    "source": doc["source"],
                    "title": doc["title"],
                    "score": final_score
                })
            
            # 7. Trier par score décroissant et prendre les 4 meilleurs
            ranked_documents.sort(key=lambda x: x["score"], reverse=True)
            best_documents = ranked_documents[:4]
            
            # 8. Formater le contexte
            context = self._format_context(best_documents)
            
            logger.info(f"Contexte récupéré avec RerankingRAGStrategy: {len(best_documents)} documents")
            return context
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du contexte avec RerankingRAGStrategy: {str(e)}")
            return ""
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """
        Calcule la similarité cosinus entre deux vecteurs.
        
        Args:
            a: Premier vecteur
            b: Deuxième vecteur
            
        Returns:
            Similarité cosinus entre les deux vecteurs
        """
        import numpy as np
        
        a = np.array(a)
        b = np.array(b)
        
        # Normaliser les vecteurs
        a_norm = np.linalg.norm(a)
        b_norm = np.linalg.norm(b)
        
        if a_norm == 0 or b_norm == 0:
            return 0.0
        
        return np.dot(a, b) / (a_norm * b_norm)

class RAGPipelineFactory:
    """Factory pour créer des stratégies RAG."""
    
    @staticmethod
    def create_strategy(strategy_type: str, user_id: str) -> RAGStrategy:
        """
        Crée une stratégie RAG en fonction du type spécifié.
        
        Args:
            strategy_type: Type de stratégie RAG
            user_id: ID de l'utilisateur
            
        Returns:
            Instance de la stratégie RAG appropriée
            
        Raises:
            ValueError: Si le type de stratégie n'est pas pris en charge
        """
        if not strategy_type:
            return BasicRAGStrategy(user_id)
            
        strategy_type = strategy_type.lower()
        
        if strategy_type == RAGStrategyEnum.BASIC.value:
            return BasicRAGStrategy(user_id)
        elif strategy_type == RAGStrategyEnum.HYBRID_SEARCH.value:
            return HybridSearchRAGStrategy(user_id)
        elif strategy_type == RAGStrategyEnum.RERANKING.value:
            return RerankingRAGStrategy(user_id)
        else:
            logger.warning(f"Stratégie RAG non reconnue: {strategy_type}, utilisation de la stratégie de base")
            return BasicRAGStrategy(user_id)