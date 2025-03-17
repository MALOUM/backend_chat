"""
Module d'orchestration du service d'ingestion des documents.

Ce module coordonne le processus complet d'ingestion de documents:
1. Chargement du document
2. Découpage en chunks
3. Génération des embeddings
4. Stockage dans la base de données vectorielle
"""

import logging
import asyncio
from typing import Dict, List, Optional, Union, Any
import uuid

from langchain.schema import Document
from app.models.document import DocumentType, DocumentMetadata
from app.ingestion_service.loader.factory import LoaderFactory
from app.ingestion_service.chunker.factory import ChunkerFactory
from app.ingestion_service.embedding.factory import EmbeddingFactory
from app.ingestion_service.vector_store.store_factory import VectorStoreFactory

logger = logging.getLogger(__name__)


class IngestionOrchestrator:
    """
    Orchestrateur du pipeline d'ingestion de documents.
    Coordonne le processus complet d'ingestion: chargement, découpage, embedding et stockage.
    """
    
    def __init__(self):
        """
        Initialise l'orchestrateur avec les factories nécessaires pour chaque étape du pipeline.
        """
        # LoaderFactory est maintenant utilisé via des méthodes statiques
        self.chunker_factory = ChunkerFactory()
        self.embedding_factory = EmbeddingFactory()
        self.vector_store_factory = VectorStoreFactory()
    
    async def process_document(
        self,
        source: str,
        document_type: DocumentType,
        user_id: str,
        document_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        chunking_strategy: str = "recursive",
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        embedding_model: str = "openai",
        embedding_model_name: Optional[str] = None,
        vector_store: str = "milvus",
        collection_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Traite un document à travers le pipeline complet d'ingestion.
        
        Args:
            source: Chemin ou URL du document
            document_type: Type du document (PDF, TEXT, URL, IMAGE)
            user_id: ID de l'utilisateur qui a soumis le document
            document_id: ID unique du document (généré automatiquement si non fourni)
            metadata: Métadonnées supplémentaires du document
            chunking_strategy: Stratégie de découpage ("recursive", "fixed", "semantic")
            chunk_size: Taille des chunks
            chunk_overlap: Chevauchement entre les chunks
            embedding_model: Type de modèle d'embedding ("openai", "huggingface", "fastembed")
            embedding_model_name: Nom spécifique du modèle d'embedding
            vector_store: Type de base de données vectorielle ("milvus", "faiss")
            collection_name: Nom de la collection dans la base vectorielle
            
        Returns:
            Dictionnaire contenant les résultats de l'ingestion
            
        Raises:
            ValueError: Si des paramètres sont invalides
            Exception: Pour toute erreur pendant le processus d'ingestion
        """
        if not document_id:
            document_id = str(uuid.uuid4())
        
        if not collection_name:
            collection_name = f"user_{user_id}_docs"
        
        start_time = asyncio.get_event_loop().time()
        
        try:
            # 1. Charger le document
            logger.info(f"Début du traitement du document {document_id} depuis {source}")
            documents = await self._load_document(source, document_type)
            
            # 2. Préparer les métadonnées
            doc_metadata = await self._prepare_metadata(
                documents, user_id, document_id, document_type, metadata
            )
            
            # 3. Découper le document en chunks
            chunks = await self._chunk_document(
                documents, chunking_strategy, chunk_size, chunk_overlap, doc_metadata
            )
            
            # 4. Créer les embeddings et stocker dans la base vectorielle
            result = await self._embed_and_store(
                chunks, embedding_model, embedding_model_name, vector_store, collection_name
            )
            
            # 5. Finaliser et renvoyer le résultat
            end_time = asyncio.get_event_loop().time()
            processing_time = end_time - start_time
            
            return {
                "document_id": document_id,
                "user_id": user_id,
                "document_type": document_type.value,
                "source": source,
                "metadata": doc_metadata,
                "chunking_strategy": chunking_strategy,
                "embedding_model": embedding_model,
                "vector_store": vector_store,
                "collection_name": collection_name,
                "num_documents": len(documents),
                "num_chunks": len(chunks),
                "processing_time_seconds": processing_time,
                "vector_ids": result.get("ids", []),
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"Erreur lors du traitement du document {document_id}: {str(e)}")
            
            # En cas d'erreur, renvoyer un dictionnaire avec les informations sur l'erreur
            end_time = asyncio.get_event_loop().time()
            processing_time = end_time - start_time
            
            return {
                "document_id": document_id,
                "user_id": user_id,
                "document_type": document_type.value,
                "source": source,
                "status": "error",
                "error": str(e),
                "processing_time_seconds": processing_time
            }
    
    async def _load_document(self, source: str, document_type: DocumentType) -> List[Document]:
        """
        Charge un document à partir d'une source.
        
        Args:
            source: Chemin ou URL vers le document
            document_type: Type de document
            
        Returns:
            Liste de documents chargés
        """
        try:
            logger.info(f"Chargement du document: {source}")
            
            # Déterminer le type de loader
            loader_type = document_type.value if hasattr(document_type, 'value') else str(document_type).lower()
            
            # Si le type est 'auto', détecter automatiquement
            if loader_type == "auto":
                loader_type = LoaderFactory.detect_loader_type(source)
                logger.info(f"Type de loader détecté automatiquement: {loader_type}")
            
            # Créer le loader approprié
            loader = await LoaderFactory.create_loader(loader_type, source)
            
            # Charger le document
            documents = await loader.load()
            
            logger.info(f"Document chargé: {source} - {len(documents)} pages/sections")
            return documents
            
        except Exception as e:
            logger.error(f"Erreur lors du chargement du document {source}: {str(e)}")
            raise
    
    async def _prepare_metadata(
        self,
        documents: List[Document],
        user_id: str,
        document_id: str,
        document_type: DocumentType,
        additional_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Prépare et enrichit les métadonnées du document.
        
        Args:
            documents: Liste de documents Langchain
            user_id: ID de l'utilisateur
            document_id: ID du document
            document_type: Type du document
            additional_metadata: Métadonnées supplémentaires
            
        Returns:
            Dictionnaire des métadonnées enrichies
        """
        try:
            # Extraire les métadonnées du premier document (si disponible)
            base_metadata = documents[0].metadata if documents and hasattr(documents[0], "metadata") else {}
            
            # Créer les métadonnées de base
            metadata = {
                "user_id": user_id,
                "document_id": document_id,
                "document_type": document_type.value,
                "num_parts": len(documents),
                **base_metadata
            }
            
            # Ajouter les métadonnées supplémentaires
            if additional_metadata:
                metadata.update(additional_metadata)
            
            logger.info(f"Métadonnées préparées pour le document {document_id}")
            return metadata
            
        except Exception as e:
            logger.error(f"Erreur lors de la préparation des métadonnées: {str(e)}")
            # En cas d'erreur, renvoyer des métadonnées minimales
            return {
                "user_id": user_id,
                "document_id": document_id,
                "document_type": document_type.value,
                "error_metadata": str(e)
            }
    
    async def _chunk_document(
        self,
        documents: List[Document],
        chunking_strategy: str,
        chunk_size: int,
        chunk_overlap: int,
        metadata: Dict[str, Any]
    ) -> List[Document]:
        """
        Découpe les documents en chunks.
        
        Args:
            documents: Liste de documents Langchain
            chunking_strategy: Stratégie de découpage
            chunk_size: Taille des chunks
            chunk_overlap: Chevauchement entre les chunks
            metadata: Métadonnées à ajouter à chaque chunk
            
        Returns:
            Liste de chunks (documents Langchain)
            
        Raises:
            Exception: Si le découpage échoue
        """
        logger.info(f"Découpage des documents avec la stratégie {chunking_strategy}")
        
        try:
            chunker = self.chunker_factory.create_chunker(
                chunking_strategy, chunk_size, chunk_overlap
            )
            
            chunks = await chunker.split(documents)
            
            # Ajouter les métadonnées à chaque chunk
            for i, chunk in enumerate(chunks):
                chunk_metadata = chunk.metadata.copy() if hasattr(chunk, "metadata") else {}
                chunk_metadata.update(metadata)
                chunk_metadata["chunk_id"] = i
                chunk.metadata = chunk_metadata
            
            logger.info(f"Documents découpés avec succès: {len(chunks)} chunks créés")
            return chunks
            
        except Exception as e:
            logger.error(f"Erreur lors du découpage des documents: {str(e)}")
            raise
    
    async def _embed_and_store(
        self,
        chunks: List[Document],
        embedding_model: str,
        embedding_model_name: Optional[str],
        vector_store: str,
        collection_name: str
    ) -> Dict[str, Any]:
        """
        Génère les embeddings pour les chunks et les stocke dans la base vectorielle.
        
        Args:
            chunks: Liste de chunks (documents Langchain)
            embedding_model: Type de modèle d'embedding
            embedding_model_name: Nom spécifique du modèle d'embedding
            vector_store: Type de base de données vectorielle
            collection_name: Nom de la collection
            
        Returns:
            Résultat de l'opération de stockage
            
        Raises:
            Exception: Si la génération d'embeddings ou le stockage échoue
        """
        logger.info(f"Génération des embeddings avec le modèle {embedding_model}")
        
        try:
            # Créer le modèle d'embedding
            embedding_model_instance = self.embedding_factory.create_embedding_model(
                embedding_model, embedding_model_name
            )
            
            # Créer la base vectorielle
            vector_db = self.vector_store_factory.create_vector_store(
                vector_store, embedding_model_instance, collection_name
            )
            
            # Stocker les chunks dans la base vectorielle
            result = await vector_db.add_documents(chunks)
            
            logger.info(f"Embeddings générés et stockés avec succès dans {collection_name}")
            return result
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération des embeddings ou du stockage: {str(e)}")
            raise


# Fonction globale pour simplifier l'utilisation
async def process_document(
    source: str,
    document_type: Union[DocumentType, str],
    user_id: str,
    **kwargs
) -> Dict[str, Any]:
    """
    Fonction utilitaire pour traiter un document à travers le pipeline complet d'ingestion.
    
    Args:
        source: Chemin ou URL du document
        document_type: Type du document (peut être une enum DocumentType ou une chaîne)
        user_id: ID de l'utilisateur qui a soumis le document
        **kwargs: Arguments supplémentaires à transmettre à l'orchestrateur
        
    Returns:
        Résultat de l'ingestion
    """
    # Convertir le type de document en enum si nécessaire
    if isinstance(document_type, str):
        document_type = DocumentType(document_type)
    
    orchestrator = IngestionOrchestrator()
    return await orchestrator.process_document(source, document_type, user_id, **kwargs) 