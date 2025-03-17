"""
Module principal pour le traitement des documents.

Ce module coordonne l'ensemble du processus de traitement des documents,
depuis le chargement initial jusqu'à la vectorisation et le stockage.
"""

import os
import logging
import tempfile
from typing import Dict, List, Optional, Tuple, Any
import uuid
import requests
from bs4 import BeautifulSoup
import json
import mimetypes
import asyncio
from datetime import datetime

# Imports LangChain
from langchain.document_loaders import PyPDFLoader, TextLoader, UnstructuredFileLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter, TokenTextSplitter
from langchain.schema import Document as LangChainDocument
from langchain.embeddings import HuggingFaceEmbeddings

from app import config
from app.models.document import Document, DocumentType, ProcessingStatus, DocumentMetadata, DocumentChunk
from app.schemas.document import ChunkingStrategy, ChunkingConfig, EmbeddingConfig
from app.db.mongodb import get_document_collection
from app.db import milvus as milvus_utils
from app.ingestion_service.loader.factory import LoaderFactory

logger = logging.getLogger(__name__)

# Fonction pour générer un ID unique
def generate_id() -> str:
    """Génère un ID unique pour les documents et chunks"""
    return str(uuid.uuid4()).replace("-", "")

# Sélection du loader approprié selon le type de document
def get_document_loader(doc_type: DocumentType, source: str):
    """
    Retourne le loader LangChain approprié selon le type de document
    
    Args:
        doc_type: Type du document
        source: Chemin ou URL du document
        
    Returns:
        Loader LangChain approprié
    """
    if doc_type == DocumentType.TEXT:
        return TextLoader(source)
    elif doc_type == DocumentType.PDF:
        return PyPDFLoader(source)
    elif doc_type == DocumentType.URL:
        return WebBaseLoader(source)
    elif doc_type == DocumentType.IMAGE:
        # Pour les images, nous utilisons UnstructuredFileLoader qui peut extraire du texte
        return UnstructuredFileLoader(source)
    else:
        raise ValueError(f"Type de document non supporté: {doc_type}")

# Sélection du text splitter selon la stratégie
def get_text_splitter(chunking_config: ChunkingConfig):
    """
    Retourne le text splitter LangChain approprié selon la configuration
    
    Args:
        chunking_config: Configuration de chunking
        
    Returns:
        Text splitter LangChain approprié
    """
    strategy = chunking_config.chunking_method
    chunk_size = chunking_config.chunk_size
    chunk_overlap = chunking_config.chunk_overlap
    
    if strategy == ChunkingStrategy.RECURSIVE:
        return RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
    elif strategy == ChunkingStrategy.FIXED_SIZE:
        return CharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
    else:
        # Par défaut, utiliser RecursiveCharacterTextSplitter
        return RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )

async def process_document(
    file_path: str,
    user_id: str,
    document_name: Optional[str] = None,
    metadata: Dict[str, Any] = None,
    chunking_config: Optional[ChunkingConfig] = None,
    embedding_config: Optional[EmbeddingConfig] = None,
    document_id: Optional[str] = None
) -> str:
    """
    Traite un document pour l'indexation et la recherche.
    
    Args:
        file_path: Chemin du fichier à traiter
        user_id: ID de l'utilisateur propriétaire
        document_name: Nom du document (optionnel)
        metadata: Métadonnées du document (optionnel)
        chunking_config: Configuration du chunking (optionnel)
        embedding_config: Configuration de l'embedding (optionnel)
        document_id: ID du document existant (optionnel)
        
    Returns:
        ID du document traité
    """
    document_collection = await get_document_collection()
    
    # Déterminer le type de document
    file_extension = os.path.splitext(file_path)[1].lower()
    if file_extension in ['.txt', '.md', '.html', '.htm', '.json', '.csv']:
        doc_type = DocumentType.TEXT
    elif file_extension in ['.pdf']:
        doc_type = DocumentType.PDF
    elif file_extension in ['.jpg', '.jpeg', '.png', '.gif']:
        doc_type = DocumentType.IMAGE
    else:
        doc_type = DocumentType.TEXT  # Utiliser TEXT comme valeur par défaut au lieu de OTHER qui n'existe pas
    
    # Générer un ID pour le document si non fourni
    if not document_id:
        document_id = generate_id()
    
    # Utiliser les configurations par défaut si non spécifiées
    if not chunking_config:
        chunking_config = ChunkingConfig(
            chunk_size=config.DEFAULT_CHUNK_SIZE,
            chunk_overlap=config.DEFAULT_CHUNK_OVERLAP,
            chunking_method=ChunkingStrategy.RECURSIVE
        )
    
    if not embedding_config:
        embedding_config = EmbeddingConfig(
            model_name=config.EMBEDDING_MODEL,
            dimension=config.EMBEDDING_DIMENSION
        )
    
    try:
        # Extraire le texte du document
        text_content = await extract_text_from_upload(file_path, doc_type)
        
        # Mettre à jour le document avec le contenu extrait
        await document_collection.update_one(
            {"_id": document_id},
            {"$set": {
                "content": text_content,
                "status": ProcessingStatus.PROCESSING,
                "updated_at": datetime.utcnow()
            }}
        )
        
        # Découper le texte en chunks
        text_splitter = get_text_splitter(chunking_config)
        chunks = text_splitter.split_text(text_content)
        
        # Créer les documents LangChain
        langchain_docs = []
        for i, chunk_text in enumerate(chunks):
            chunk_id = generate_id()
            langchain_doc = LangChainDocument(
                page_content=chunk_text,
                metadata={
                    "document_id": document_id,
                    "chunk_id": chunk_id,
                    "chunk_index": i,
                    "source": file_path
                }
            )
            langchain_docs.append(langchain_doc)
        
        # Créer le modèle d'embedding
        from app.ingestion_service.embedding.openai_embedding import OpenAIEmbedding
        
        model_name = "second-state/All-MiniLM-L6-v2-Embedding-GGUF"
        model = OpenAIEmbedding(
            model_name=model_name,
            api_key="lm-studio",
            base_url="http://host.docker.internal:1234/v1"
        )
        
        # Générer les embeddings
        embeddings = await model.embed_documents([doc.page_content for doc in langchain_docs])
        
        # Afficher des informations de débogage
        logger.info(f"Embeddings générés avec succès: {len(embeddings)} embeddings de dimension {len(embeddings[0])}")
        
        # S'assurer que la connexion à Milvus est établie
        connected = await milvus_utils.connect_to_milvus()
        if not connected:
            logger.error("Impossible de se connecter à Milvus")
            raise Exception("Impossible de se connecter à Milvus")
        
        # Récupérer ou créer la collection Milvus
        try:
            collection = await milvus_utils.get_collection(
                collection_name=config.MILVUS_COLLECTION,
                create_if_missing=True,
                dimension=len(embeddings[0])  # Utiliser la dimension réelle des embeddings
            )
            
            if not collection:
                logger.error("Collection Milvus non disponible")
                raise Exception("Impossible de récupérer ou créer la collection Milvus")
                
            logger.info(f"Collection Milvus récupérée: {config.MILVUS_COLLECTION}")
        except Exception as e:
            logger.error(f"Erreur lors de la récupération de la collection Milvus: {str(e)}")
            raise Exception(f"Impossible de récupérer ou créer la collection Milvus: {str(e)}")
        
        # Préparer les données pour l'insertion
        ids = [doc.metadata["chunk_id"] for doc in langchain_docs]
        document_ids = [doc.metadata["document_id"] for doc in langchain_docs]
        chunk_ids = [doc.metadata["chunk_id"] for doc in langchain_docs]
        contents = [doc.page_content for doc in langchain_docs]
        
        try:
            # Vérifier la cohérence des données avant insertion
            assert len(ids) == len(document_ids) == len(chunk_ids) == len(contents) == len(embeddings), "Les longueurs des listes ne correspondent pas !"
            assert all(isinstance(embed, list) and all(isinstance(x, float) for x in embed) for embed in embeddings), "Format des embeddings incorrect !"
            assert all(len(embed) == config.EMBEDDING_DIMENSION for embed in embeddings), "Les embeddings ont une dimension incorrecte !"

            # Transformer en format attendu par Milvus
            insert_data = [
                ids, document_ids, chunk_ids, contents, embeddings
            ]

            # Insérer dans Milvus
            collection.insert(insert_data)
            logger.info(f"Inséré {len(ids)} embeddings dans Milvus")
            
        except Exception as e:
            logger.error(f"Erreur lors de l'insertion dans Milvus: {str(e)}")
            raise

        
        # Mettre à jour le document avec les informations de traitement
        logger.info(f"Tentative de mise à jour du statut du document {document_id} vers COMPLETED")
        
        # Essayer de trouver le document par son ID
        update_result = await document_collection.update_one(
            {"_id": document_id},
            {"$set": {
                "status": ProcessingStatus.COMPLETED,
                "metadata.chunks_count": len(chunks),
                "updated_at": datetime.utcnow()
            }}
        )
        
        # Si le document n'a pas été trouvé, essayer de le trouver par son ID original dans les métadonnées
        if update_result.matched_count == 0:
            logger.warning(f"Document non trouvé avec ID direct: {document_id}, recherche par ID original dans les métadonnées")
            update_result = await document_collection.update_one(
                {"metadata.properties.original_id": document_id},
                {"$set": {
                    "status": ProcessingStatus.COMPLETED,
                    "metadata.chunks_count": len(chunks),
                    "updated_at": datetime.utcnow()
                }}
            )
            
            # Si toujours pas trouvé, essayer de trouver tous les documents de l'utilisateur
            if update_result.matched_count == 0:
                logger.warning(f"Document non trouvé avec ID original: {document_id}, recherche dans tous les documents")
                # Récupérer tous les documents
                cursor = document_collection.find({})
                async for doc in cursor:
                    # Vérifier si l'ID correspond
                    if str(doc.get("_id")) == document_id:
                        update_result = await document_collection.update_one(
                            {"_id": doc.get("_id")},
                            {"$set": {
                                "status": ProcessingStatus.COMPLETED,
                                "metadata.chunks_count": len(chunks),
                                "updated_at": datetime.utcnow()
                            }}
                        )
                        break
                    # Vérifier si l'ID original correspond
                    original_id = doc.get("metadata", {}).get("properties", {}).get("original_id")
                    if original_id and original_id == document_id:
                        update_result = await document_collection.update_one(
                            {"_id": doc.get("_id")},
                            {"$set": {
                                "status": ProcessingStatus.COMPLETED,
                                "metadata.chunks_count": len(chunks),
                                "updated_at": datetime.utcnow()
                            }}
                        )
                        break
        
        logger.info(f"Résultat de la mise à jour: matched={update_result.matched_count}, modified={update_result.modified_count}")
        
        # Vérifier si le document a été mis à jour
        updated_doc = await document_collection.find_one({"metadata.properties.original_id": document_id})
        if updated_doc:
            logger.info(f"Statut du document après mise à jour: {updated_doc.get('status')}")
        else:
            logger.warning(f"Document {document_id} non trouvé après mise à jour")
        
        logger.info(f"Document {document_id} traité avec succès - {len(chunks)} chunks générés")
        
        # Supprimer le fichier temporaire si nécessaire
        if os.path.exists(file_path) and file_path.startswith(tempfile.gettempdir()):
            os.remove(file_path)
            logger.debug(f"Fichier temporaire supprimé: {file_path}")
        
        return document_id
        
    except Exception as e:
        logger.error(f"Erreur lors du traitement du document: {str(e)}")
        
        # Mettre à jour le document avec l'erreur
        await document_collection.update_one(
            {"_id": document_id},
            {"$set": {
                "status": ProcessingStatus.FAILED,
                "metadata.error": str(e),
                "updated_at": datetime.utcnow()
            }}
        )
        
        # Supprimer le fichier temporaire en cas d'erreur
        if os.path.exists(file_path) and file_path.startswith(tempfile.gettempdir()):
            os.remove(file_path)
        
        raise

async def process_url(
    url: str,
    user_id: str,
    metadata: Dict[str, Any] = None,
    chunking_config: Optional[ChunkingConfig] = None,
    embedding_config: Optional[EmbeddingConfig] = None
) -> str:
    """
    Traite une URL pour l'indexation RAG.
    
    Args:
        url: URL à traiter
        user_id: ID de l'utilisateur
        metadata: Métadonnées supplémentaires
        chunking_config: Configuration de chunking (optionnel)
        embedding_config: Configuration d'embedding (optionnel)
        
    Returns:
        ID du document créé
    """
    try:
        document_collection = await get_document_collection()
        
        logger.info(f"Traitement de l'URL : {url}")
        
        # Créer l'ID du document
        document_id = generate_id()
        now = datetime.utcnow()
        
        # Extraire le titre de la page si possible
        title = url
        try:
            response = requests.get(url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            if soup.title and soup.title.string:
                title = soup.title.string.strip()
        except Exception as e:
            logger.warning(f"Impossible d'extraire le titre de la page : {str(e)}")
        
        # Créer le document dans MongoDB avec statut PENDING
        doc_metadata = DocumentMetadata(
            source=url,
            **(metadata or {})
        )
        
        document = Document(
            _id=document_id,
            user_id=user_id,
            title=title,
            type=DocumentType.URL,
            content="",  # Sera rempli après traitement
            url=url,
            status=ProcessingStatus.PROCESSING,
            metadata=doc_metadata,
            created_at=now,
            updated_at=now
        )
        
        await document_collection.insert_one(document.dict(by_alias=True))
        
        # Utiliser les configurations par défaut si non fournies
        if not chunking_config:
            chunking_config = ChunkingConfig(
                chunk_size=config.DEFAULT_CHUNK_SIZE,
                chunk_overlap=config.DEFAULT_CHUNK_OVERLAP,
                chunking_method=ChunkingStrategy.RECURSIVE
            )
        
        if not embedding_config:
            embedding_config = EmbeddingConfig(
                model_name=config.EMBEDDING_MODEL,
                dimension=config.EMBEDDING_DIMENSION
            )
        
        # Charger la page web avec LangChain
        try:
            loader = WebBaseLoader(url)
            langchain_docs = loader.load()
            
            # Extraire le texte complet pour le stocker dans le document
            full_text = "\n\n".join([doc.page_content for doc in langchain_docs])
            
            # Mettre à jour le document avec le contenu
            await document_collection.update_one(
                {"_id": document_id},
                {"$set": {"content": full_text}}
            )
            
            # Découper le document en chunks
            text_splitter = get_text_splitter(chunking_config)
            chunks = text_splitter.split_documents(langchain_docs)
            
            logger.info(f"URL découpée en {len(chunks)} chunks")
            
            # Créer les chunks dans MongoDB
            chunk_ids = []
            chunk_texts = []
            chunk_metadatas = []
            
            for i, chunk in enumerate(chunks):
                chunk_id = generate_id()
                chunk_ids.append(chunk_id)
                
                # Préparer les données pour l'embedding
                chunk_texts.append(chunk.page_content)
                chunk_metadatas.append({
                    "document_id": document_id,
                    "chunk_id": chunk_id,
                    **chunk.metadata
                })
                
                # Créer le chunk dans MongoDB
                doc_chunk = DocumentChunk(
                    _id=chunk_id,
                    document_id=document_id,
                    chunk_index=i,
                    content=chunk.page_content,
                    metadata=chunk.metadata
                )
                
                await document_collection.database["document_chunks"].insert_one(
                    doc_chunk.dict(by_alias=True)
                )
            
            # Créer les embeddings avec Milvus
            try:
                # Vérifier la connexion à Milvus
                await milvus_utils.connect_to_milvus()
                
                # Insérer les embeddings
                embedding_ids = await milvus_utils.insert_embeddings({
                    "texts": chunk_texts,
                    "metadatas": chunk_metadatas,
                    "model": embedding_config.model_name,
                    "dimension": embedding_config.dimension
                })
                
                # Mettre à jour les chunks avec les IDs d'embedding
                for i, chunk_id in enumerate(chunk_ids):
                    if i < len(embedding_ids):
                        await document_collection.database["document_chunks"].update_one(
                            {"_id": chunk_id},
                            {"$set": {"embedding_id": embedding_ids[i]}}
                        )
                
                # Mettre à jour le document avec statut COMPLETED
                await document_collection.update_one(
                    {"_id": document_id},
                    {
                        "$set": {
                            "status": ProcessingStatus.COMPLETED,
                            "updated_at": datetime.utcnow(),
                            "metadata.properties.chunks_count": len(chunks)
                        }
                    }
                )
                
                logger.info(f"URL traitée avec succès, ID : {document_id}")
                
            except Exception as e:
                logger.error(f"Erreur lors de la création des embeddings : {str(e)}")
                # Mettre à jour le document avec statut FAILED
                await document_collection.update_one(
                    {"_id": document_id},
                    {
                        "$set": {
                            "status": ProcessingStatus.FAILED,
                            "updated_at": datetime.utcnow(),
                            "metadata.properties.error": str(e)
                        }
                    }
                )
                raise
                
        except Exception as e:
            logger.error(f"Erreur lors du chargement ou chunking de l'URL : {str(e)}")
            # Mettre à jour le document avec statut FAILED
            await document_collection.update_one(
                {"_id": document_id},
                {
                    "$set": {
                        "status": ProcessingStatus.FAILED,
                        "updated_at": datetime.utcnow(),
                        "metadata.properties.error": str(e)
                    }
                }
            )
            raise
        
        return document_id
        
    except Exception as e:
        logger.error(f"Erreur lors du traitement de l'URL : {str(e)}")
        raise

async def extract_text_from_upload(file_path: str, document_type: DocumentType) -> str:
    """
    Extrait le texte d'un fichier téléchargé.
    
    Args:
        file_path: Chemin du fichier
        document_type: Type de document
        
    Returns:
        Texte extrait du document
    """
    try:
        # Convertir DocumentType en chaîne pour le loader
        doc_type_str = document_type.value if hasattr(document_type, 'value') else str(document_type).lower()
        
        # Créer le loader approprié
        loader = await LoaderFactory.create_loader(doc_type_str, file_path)
        
        # Charger le document
        documents = await loader.load()
        
        # Concaténer le contenu de tous les documents
        text_content = "\n\n".join([doc.page_content for doc in documents])
        
        return text_content
        
    except Exception as e:
        logger.error(f"Erreur lors de l'extraction du texte depuis {file_path}: {str(e)}")
        raise

async def process_text_to_chunks(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    chunking_method: str = "recursive"
) -> List[Any]:
    """
    Découpe un texte en chunks pour le traitement.
    
    Args:
        text: Texte à découper
        chunk_size: Taille des chunks
        chunk_overlap: Chevauchement des chunks
        chunking_method: Méthode de chunking (recursive, fixed_size, etc.)
    
    Returns:
        Liste des chunks de texte
    """
    logger.info(f"Découpage du texte avec la méthode {chunking_method}, taille={chunk_size}, chevauchement={chunk_overlap}")
    
    # Créer le text splitter en fonction de la méthode spécifiée
    if chunking_method == "recursive" or chunking_method == "fixed_size":
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
    else:
        # Par défaut, utiliser CharacterTextSplitter
        text_splitter = CharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
    
    # Créer un document simple
    doc = LangChainDocument(page_content=text)
    
    # Diviser le document en chunks
    chunks = text_splitter.split_documents([doc])
    
    logger.info(f"Texte découpé en {len(chunks)} chunks")
    return chunks 