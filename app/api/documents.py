from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks, File, UploadFile, Form, Query
from typing import List, Optional, Any, Dict
from datetime import datetime
import uuid
import json
import os
import aiofiles
import logging
import tempfile
from pydantic import HttpUrl, BaseModel, Field
from bson import ObjectId
import numpy as np

from app.dependencies import get_current_active_user
from app.models.user import UserInDB
from app.models.document import Document, DocumentType, ProcessingStatus, DocumentMetadata
from app.schemas.document import (
    DocumentCreate, DocumentUpdate, DocumentResponse,
    DocumentChunkResponse, ChunkingStrategy, ChunkingConfig,
    EmbeddingConfig, ProcessingRequest, ProcessingResponse
)
from app.db.mongodb import get_document_collection
from app.core.document_processor import process_document, process_url, extract_text_from_upload, generate_id
from app.db import milvus as milvus_utils
from app import config

# Import des services d'ingestion
from app.ingestion_service.orchestrator import IngestionOrchestrator
from app.ingestion_service.loader.factory import LoaderFactory
from app.ingestion_service.chunker.factory import ChunkerFactory
from app.ingestion_service.embedding.factory import EmbeddingFactory
from app.ingestion_service.vector_store.store_factory import VectorStoreFactory

logger = logging.getLogger(__name__)

# Modèles de données pour l'ingestion
class IngestionParams(BaseModel):
    """Paramètres de configuration pour l'ingestion de documents."""
    chunker_type: str = Field("recursive", description="Type de chunker à utiliser")
    embedding_type: str = Field("openai", description="Type d'embedding à utiliser")
    store_type: str = Field("milvus", description="Type de store vectoriel à utiliser")
    chunk_size: int = Field(1000, description="Taille des chunks (nombre de caractères)")
    chunk_overlap: int = Field(200, description="Chevauchement entre les chunks")
    collection_name: Optional[str] = Field(None, description="Nom de la collection (généré automatiquement si non spécifié)")

class IngestionResponse(BaseModel):
    """Réponse à une requête d'ingestion."""
    document_id: str = Field(..., description="ID du document")
    task_id: Optional[str] = Field(None, description="ID de la tâche d'ingestion (si asynchrone)")
    status: str = Field(..., description="Statut de l'ingestion (pending, success, error)")
    source: str = Field(..., description="Source du document")
    num_pages: Optional[int] = Field(None, description="Nombre de pages du document")
    num_chunks: Optional[int] = Field(None, description="Nombre de chunks générés")
    processing_time: Optional[float] = Field(None, description="Temps de traitement en secondes")
    error: Optional[str] = Field(None, description="Message d'erreur (si status=error)")

# Stockage des tâches en cours (en mémoire pour cet exemple)
# Dans une application réelle, utiliser une base de données ou Redis
TASKS = {}

# Nouveaux schémas pour la recherche
class SearchResult(BaseModel):
    """Résultat de recherche de documents"""
    document_id: str
    chunk_id: str
    content: str
    score: float
    document_title: Optional[str] = None
    document_type: Optional[str] = None

class SearchResponse(BaseModel):
    """Réponse de recherche avec pagination"""
    results: List[SearchResult]
    total: int
    query: str

class SearchQuery(BaseModel):
    """Requête de recherche."""
    query: str = Field(..., description="Requête textuelle")
    document_id: Optional[str] = Field(None, description="ID du document (pour filtrer)")
    max_results: int = Field(4, description="Nombre maximum de résultats")

router = APIRouter(prefix="/documents", tags=["Documents"])

@router.get("/search-documents", response_model=SearchResponse)
async def search_documents(
    query: str,
    top_k: int = Query(5, ge=1, le=20),
    embedding_model: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    document_type: Optional[DocumentType] = Query(None),
    current_user: UserInDB = Depends(get_current_active_user)
) -> Any:
    """
    Recherche sémantique dans les documents.
    
    Permet de rechercher des documents par similarité sémantique avec la requête.
    
    Args:
        query: Texte de la requête
        top_k: Nombre de résultats à retourner
        embedding_model: Modèle d'embedding à utiliser (optionnel)
        user_id: Filtrer par utilisateur (optionnel)
        document_type: Filtrer par type de document (optionnel)
        current_user: Utilisateur connecté
    """
    logger.info(f"Recherche de documents avec la requête: {query}")
    document_collection = await get_document_collection()
    
    # Si aucun utilisateur spécifique n'est demandé, filtrer par l'utilisateur actuel
    target_user_id = user_id or current_user.id
    
    # Vérifier que la requête n'est pas vide
    if not query or len(query.strip()) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La requête ne peut pas être vide"
        )
    
    # S'assurer que la connexion à Milvus est établie
    connected = await milvus_utils.connect_to_milvus()
    if not connected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Le service de recherche vectorielle n'est pas disponible"
        )
    
    # Obtenir le modèle d'embedding
    try:
        # Utiliser OpenAI embedding
        embedding_factory = EmbeddingFactory()
        embedding_model = embedding_factory.create_embedding_model("openai")
        
        # Générer l'embedding de la requête
        logger.info(f"Génération d'un embedding pour la recherche avec OpenAI")
        query_embedding = await embedding_model.embed_query(query)
        
        # Récupérer la collection Milvus
        collection = await milvus_utils.get_collection(config.MILVUS_COLLECTION)
        if not collection:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="La collection de vecteurs n'est pas disponible"
            )
        
        # Rechercher dans Milvus
        search_params = {"metric_type": "L2", "params": {"ef": 64}}
        search_results = collection.search(
            data=[query_embedding],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            output_fields=["document_id", "chunk_id", "content"]
        )
        
        if not search_results or len(search_results[0]) == 0:
            return {
                "results": [],
                "total": 0,
                "query": query
            }
        
        # Traiter les résultats
        results = []
        for hits in search_results:
            for hit in hits:
                chunk_id = hit.entity.get("chunk_id")
                document_id = hit.entity.get("document_id")
                content = hit.entity.get("content")
                score = hit.distance
                
                # Récupérer les informations du document
                document = await document_collection.find_one({"_id": document_id})
                
                # Filtrer par type de document si spécifié
                if document_type and document and document.get("type") != document_type:
                    continue
                
                # Filtrer par utilisateur
                if document and document.get("user_id") != target_user_id:
                    continue
                
                # Création du résultat
                result = SearchResult(
                    document_id=document_id,
                    chunk_id=chunk_id,
                    content=content,
                    score=score,
                    document_title=document.get("title") if document else None,
                    document_type=document.get("type") if document else None
                )
                
                results.append(result)
        
        return {
            "results": results,
            "total": len(results),
            "query": query
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de la recherche de documents: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la recherche: {str(e)}"
        )

@router.post("/search-advanced", response_model=SearchResponse)
async def search_documents_advanced(
    query: SearchQuery,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    Recherche avancée de documents avec filtrage et options supplémentaires.
    Utilise un modèle d'embedding pour trouver les documents les plus similaires.
    
    Args:
        query: Paramètres de recherche
        current_user: Utilisateur actuel
        
    Returns:
        Résultats de recherche avec pagination
    """
    try:
        logger.info(f"Recherche avancée de documents avec la requête: {query.query}")
        
        # Créer le modèle d'embedding
        embedding_factory = EmbeddingFactory()
        embedding_model = embedding_factory.create_embedding_model("openai")
        
        # Créer le store vectoriel
        vector_store_factory = VectorStoreFactory()
        # Utiliser la collection globale au lieu de la collection spécifique à l'utilisateur
        collection_name = "document_embeddings"
        vector_store = await vector_store_factory.create_vector_store(
            "milvus",
            embedding_model,
            collection_name
        )
        
        # Préparer les filtres si nécessaire
        filter_dict = {}
        if query.document_id:
            filter_dict["document_id"] = query.document_id
        
        # Effectuer la recherche
        results = await vector_store.similarity_search(
            query.query,
            k=query.max_results,
            filter=filter_dict
        )
        
        # Convertir les résultats en format de réponse
        search_results = []
        for doc in results:
            search_results.append(
                SearchResult(
                    document_id=doc.metadata.get("document_id", ""),
                    chunk_id=doc.metadata.get("chunk_id", ""),
                    content=doc.page_content,
                    score=doc.metadata.get("score", 0.0),
                    document_title=None,  # Ces informations ne sont pas disponibles dans les métadonnées
                    document_type=None    # Ces informations ne sont pas disponibles dans les métadonnées
                )
            )
        
        return SearchResponse(
            results=search_results,
            total=len(search_results),
            query=query.query
        )
        
    except Exception as e:
        logger.error(f"Erreur lors de la recherche avancée: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la recherche: {str(e)}"
        )

@router.post("", response_model=DocumentResponse)
async def create_document(
    document_data: DocumentCreate,
    background_tasks: BackgroundTasks,
    current_user: UserInDB = Depends(get_current_active_user)
) -> Any:
    """
    Créer un nouveau document à partir de contenu texte ou URL.
    """
    document_collection = await get_document_collection()
    
    document_id = str(uuid.uuid4())
    now = datetime.utcnow()
    
    # Vérifier si on a au moins un contenu ou une URL
    if not document_data.content and not document_data.url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le contenu ou l'URL du document est requis"
        )
    
    if document_data.type == DocumentType.URL and not document_data.url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="L'URL est requise pour le type URL"
        )
    
    # Créer les métadonnées
    metadata = document_data.metadata or DocumentMetadata()
    
    # Stocker l'ID original dans les métadonnées
    if not metadata.properties:
        metadata.properties = {}
    metadata.properties["original_id"] = document_id
    
    # Créer le document
    new_document = Document(
        _id=document_id,
        user_id=current_user.id,
        title=document_data.title,
        type=document_data.type,
        content=document_data.content or "",
        url=str(document_data.url) if document_data.url else None,
        status=ProcessingStatus.PENDING,
        metadata=metadata,
        created_at=now,
        updated_at=now
    )
    
    await document_collection.insert_one(new_document.dict(by_alias=True))
    
    # Traitement asynchrone du document
    if document_data.type == DocumentType.URL:
        background_tasks.add_task(
            process_url,
            url=str(document_data.url),
            user_id=current_user.id,
            metadata=document_data.metadata.dict() if document_data.metadata else {}
        )
    else:
        # Sauvegarder le contenu dans un fichier temporaire
        temp_file_path = os.path.join(config.TEMP_DIR, f"{document_id}.txt")
        async with aiofiles.open(temp_file_path, 'w', encoding='utf-8') as f:
            await f.write(document_data.content or "")
        
        # Lancer le traitement avec le fichier temporaire
        background_tasks.add_task(
            process_document,
            file_path=temp_file_path,
            user_id=current_user.id,
            document_name=document_data.title,
            metadata=document_data.metadata.dict() if document_data.metadata else {},
            document_id=document_id
        )
    
    return {
        "id": document_id,
        "user_id": current_user.id,
        "title": new_document.title,
        "type": new_document.type,
        "url": new_document.url,
        "status": new_document.status,
        "metadata": new_document.metadata,
        "created_at": new_document.created_at,
        "updated_at": new_document.updated_at
    }

@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    file: UploadFile = File(...),
    metadata: Optional[str] = Form(None),
    chunking_method: Optional[ChunkingStrategy] = Form(ChunkingStrategy.RECURSIVE),
    chunk_size: Optional[int] = Form(config.DEFAULT_CHUNK_SIZE),
    chunk_overlap: Optional[int] = Form(config.DEFAULT_CHUNK_OVERLAP),
    embedding_model: Optional[str] = Form(config.EMBEDDING_MODEL),
    process_now: Optional[bool] = Form(True),
    current_user: UserInDB = Depends(get_current_active_user)
) -> Any:
    """
    Télécharger et traiter un fichier document.
    
    Args:
        title: Titre du document
        file: Fichier à télécharger
        metadata: Métadonnées au format JSON (optionnel)
        chunking_method: Méthode de chunking (recursive, fixed_size, etc.)
        chunk_size: Taille des chunks
        chunk_overlap: Chevauchement des chunks
        embedding_model: Modèle d'embedding à utiliser
        process_now: Si True, le document est traité immédiatement après l'upload
        current_user: Utilisateur connecté
    """
    document_collection = await get_document_collection()
    
    document_id = generate_id()
    now = datetime.utcnow()
    
    # Déterminer le type du document
    file_extension = os.path.splitext(file.filename)[1].lower()
    if file_extension in ['.txt', '.md', '.html', '.htm', '.json', '.csv']:
        doc_type = DocumentType.TEXT
    elif file_extension in ['.pdf']:
        doc_type = DocumentType.PDF
    elif file_extension in ['.jpg', '.jpeg', '.png', '.gif']:
        doc_type = DocumentType.IMAGE
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Type de fichier non pris en charge"
        )
    
    # Sauvegarder le fichier temporairement
    temp_file_path = os.path.join(config.TEMP_DIR, f"{document_id}{file_extension}")
    
    async with aiofiles.open(temp_file_path, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)
    
    # Extraire le texte du fichier
    try:
        text_content = await extract_text_from_upload(temp_file_path, doc_type)
    except Exception as e:
        # Supprimer le fichier temporaire en cas d'erreur
        os.remove(temp_file_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'extraction du texte: {str(e)}"
        )
    
    # Créer le document
    parsed_metadata = DocumentMetadata()
    if metadata:
        try:
            metadata_dict = json.loads(metadata)
            # Ajouter des informations sur le fichier original
            metadata_dict["source"] = file.filename
            metadata_dict["properties"] = metadata_dict.get("properties", {})
            metadata_dict["properties"]["original_filename"] = file.filename
            metadata_dict["properties"]["file_extension"] = file_extension
            metadata_dict["properties"]["file_size"] = len(content)
            
            parsed_metadata = DocumentMetadata(**metadata_dict)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Format JSON invalide pour les métadonnées"
            )
    else:
        # Créer des métadonnées par défaut
        parsed_metadata = DocumentMetadata(
            source=file.filename,
            properties={
                "original_filename": file.filename,
                "file_extension": file_extension,
                "file_size": len(content)
            }
        )
    
    # Créer le document dans MongoDB (avec un statut initial)
    status_initial = ProcessingStatus.PENDING
    
    new_document = Document(
        _id=document_id,
        user_id=current_user.id,
        title=title or file.filename,
        type=doc_type,
        content=text_content,
        status=status_initial,
        metadata=parsed_metadata,
        created_at=now,
        updated_at=now
    )
    
    # Stocker l'ID original dans les métadonnées
    if not parsed_metadata.properties:
        parsed_metadata.properties = {}
    parsed_metadata.properties["original_id"] = document_id
    new_document.metadata = parsed_metadata
    
    await document_collection.insert_one(new_document.dict(by_alias=True))
    
    # Si demandé, traiter le document maintenant
    if process_now:
        # Configurer le chunking
        chunking_config = ChunkingConfig(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            chunking_method=chunking_method
        )
        
        # Configurer l'embedding
        embedding_config = EmbeddingConfig(
            model_name=embedding_model,
            dimension=config.EMBEDDING_DIMENSION
        )
        
        # Lancer le traitement en arrière-plan
        background_tasks.add_task(
            process_document,
            file_path=temp_file_path,
            user_id=current_user.id,
            document_name=title or file.filename,
            metadata=parsed_metadata.dict(),
            chunking_config=chunking_config,
            embedding_config=embedding_config,
            document_id=document_id
        )
    else:
        # Si on ne traite pas maintenant, supprimer le fichier temporaire
        os.remove(temp_file_path)
    
    # Préparer la réponse
    return {
        "id": document_id,
        "user_id": current_user.id,
        "title": new_document.title,
        "type": new_document.type,
        "url": new_document.url,
        "status": new_document.status,
        "metadata": new_document.metadata,
        "created_at": new_document.created_at,
        "updated_at": new_document.updated_at
    }

@router.get("", response_model=List[DocumentResponse])
async def get_documents(
    current_user: UserInDB = Depends(get_current_active_user),
    skip: int = 0,
    limit: int = 20
) -> Any:
    """
    Récupérer tous les documents de l'utilisateur.
    """
    document_collection = await get_document_collection()
    
    documents = []
    cursor = document_collection.find(
        {"user_id": current_user.id}
    ).sort("created_at", -1).skip(skip).limit(limit)
    
    async for doc in cursor:
        # Convertir l'ObjectId en chaîne si nécessaire
        if isinstance(doc["_id"], ObjectId):
            doc["_id"] = str(doc["_id"])
        
        documents.append({
            "id": doc["_id"],
            "user_id": doc["user_id"],
            "title": doc["title"],
            "type": doc["type"],
            "url": doc.get("url"),
            "status": doc["status"],
            "metadata": doc["metadata"],
            "created_at": doc["created_at"],
            "updated_at": doc["updated_at"]
        })
    
    return documents

@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    current_user: UserInDB = Depends(get_current_active_user)
) -> Any:
    """
    Récupérer un document spécifique.
    """
    document_collection = await get_document_collection()
    
    # Log pour déboguer
    logger.info(f"Recherche du document avec ID: {document_id}")
    
    # Essayer différentes formes d'ID (ObjectId ou chaîne)
    document = None
    
    # Essai 1: Recherche directe par ID (sans conversion)
    document = await document_collection.find_one({
        "_id": document_id,
        "user_id": current_user.id
    })
    
    # Essai 2: Si ObjectId est valide, essayer avec ObjectId
    if not document and ObjectId.is_valid(document_id):
        try:
            document = await document_collection.find_one({
                "_id": ObjectId(document_id),
                "user_id": current_user.id
            })
        except Exception as e:
            logger.warning(f"Erreur lors de la conversion en ObjectId: {e}")
    
    # Essai 3: Si le document n'est toujours pas trouvé, essayer avec une forme normalisée (sans tirets)
    if not document and "-" in document_id:
        normalized_id = document_id.replace("-", "")
        document = await document_collection.find_one({
            "_id": normalized_id,
            "user_id": current_user.id
        })
    
    # Essai 4: Rechercher par ID original dans les métadonnées
    if not document:
        logger.info(f"Document non trouvé avec ID exact, recherche par ID original dans les métadonnées")
        document = await document_collection.find_one({
            "metadata.properties.original_id": document_id,
            "user_id": current_user.id
        })
    
    # Essai 5: Rechercher par ID dans tous les documents de l'utilisateur
    if not document:
        logger.info(f"Document non trouvé avec ID original, recherche dans tous les documents de l'utilisateur")
        cursor = document_collection.find({"user_id": current_user.id})
        async for doc in cursor:
            logger.info(f"Document trouvé: ID={doc['_id']}, titre={doc['title']}")
            if str(doc['_id']) == document_id:
                document = doc
                break
            # Vérifier aussi dans les métadonnées
            if doc.get('metadata', {}).get('properties', {}).get('original_id') == document_id:
                document = doc
                break
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document non trouvé"
        )
    
    # S'assurer que l'ID est une chaîne
    if isinstance(document["_id"], ObjectId):
        document["_id"] = str(document["_id"])
    
    # Ajouter l'ID original dans la réponse si disponible
    original_id = document.get("metadata", {}).get("properties", {}).get("original_id")
    if original_id and original_id != document["_id"]:
        if not document["metadata"].get("properties"):
            document["metadata"]["properties"] = {}
        document["metadata"]["properties"]["original_id"] = original_id
        
    return {
        "id": document["_id"],
        "user_id": document["user_id"],
        "title": document["title"],
        "type": document["type"],
        "url": document.get("url"),
        "status": document["status"],
        "metadata": document["metadata"],
        "created_at": document["created_at"],
        "updated_at": document["updated_at"]
    }

@router.put("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: str,
    document_data: DocumentUpdate,
    background_tasks: BackgroundTasks,
    current_user: UserInDB = Depends(get_current_active_user)
) -> Any:
    """
    Mettre à jour un document.
    """
    document_collection = await get_document_collection()
    
    # Log pour déboguer
    logger.info(f"Tentative de mise à jour du document avec ID: {document_id}")
    
    # Essayer différentes formes d'ID (ObjectId ou chaîne)
    document = None
    
    # Essai 1: Recherche directe par ID (sans conversion)
    document = await document_collection.find_one({
        "_id": document_id,
        "user_id": current_user.id
    })
    
    # Essai 2: Si ObjectId est valide, essayer avec ObjectId
    if not document and ObjectId.is_valid(document_id):
        try:
            document = await document_collection.find_one({
                "_id": ObjectId(document_id),
                "user_id": current_user.id
            })
        except Exception as e:
            logger.warning(f"Erreur lors de la conversion en ObjectId: {e}")
    
    # Essai 3: Si le document n'est toujours pas trouvé, essayer avec une forme normalisée (sans tirets)
    if not document and "-" in document_id:
        normalized_id = document_id.replace("-", "")
        document = await document_collection.find_one({
            "_id": normalized_id,
            "user_id": current_user.id
        })
    
    # Essai 4: Rechercher par ID original dans les métadonnées
    if not document:
        logger.info(f"Document non trouvé avec ID exact, recherche par ID original dans les métadonnées")
        document = await document_collection.find_one({
            "metadata.properties.original_id": document_id,
            "user_id": current_user.id
        })
    
    # Essai 5: Rechercher par ID dans tous les documents de l'utilisateur
    if not document:
        logger.info(f"Document non trouvé avec ID original, recherche dans tous les documents de l'utilisateur")
        cursor = document_collection.find({"user_id": current_user.id})
        async for doc in cursor:
            if str(doc['_id']) == document_id:
                document = doc
                break
            # Vérifier aussi dans les métadonnées
            if doc.get('metadata', {}).get('properties', {}).get('original_id') == document_id:
                document = doc
                break
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document non trouvé"
        )
    
    # Récupérer l'ID réel du document dans MongoDB
    real_id = document["_id"]
    
    update_data = {k: v for k, v in document_data.dict(exclude_unset=True).items() if v is not None}
    
    if update_data:
        update_data["updated_at"] = datetime.utcnow()
        update_data["status"] = ProcessingStatus.PENDING
        
        await document_collection.update_one(
            {"_id": real_id},
            {"$set": update_data}
        )
        
        # Re-traiter le document si le contenu a changé
        if "content" in update_data:
            background_tasks.add_task(
                process_document,
                document_id=str(real_id)
            )
    
    updated_document = await document_collection.find_one({"_id": real_id})
    
    # S'assurer que l'ID est une chaîne
    if isinstance(updated_document["_id"], ObjectId):
        updated_document["_id"] = str(updated_document["_id"])
    
    # Ajouter l'ID original dans la réponse si disponible
    original_id = updated_document.get("metadata", {}).get("properties", {}).get("original_id")
    if original_id and original_id != updated_document["_id"]:
        if not updated_document["metadata"].get("properties"):
            updated_document["metadata"]["properties"] = {}
        updated_document["metadata"]["properties"]["original_id"] = original_id
    
    return {
        "id": updated_document["_id"],
        "user_id": updated_document["user_id"],
        "title": updated_document["title"],
        "type": updated_document["type"],
        "url": updated_document.get("url"),
        "status": updated_document["status"],
        "metadata": updated_document["metadata"],
        "created_at": updated_document["created_at"],
        "updated_at": updated_document["updated_at"]
    }

@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    current_user: UserInDB = Depends(get_current_active_user)
) -> None:
    """
    Supprimer un document.
    """
    document_collection = await get_document_collection()
    
    # Essayer différentes formes d'ID (ObjectId ou chaîne)
    document = None
    
    # Essai 1: Recherche directe par ID (sans conversion)
    logger.info(f"Tentative de suppression du document avec ID: {document_id}")
    document = await document_collection.find_one({
        "_id": document_id,
        "user_id": current_user.id
    })
    
    # Essai 2: Si ObjectId est valide, essayer avec ObjectId
    if not document and ObjectId.is_valid(document_id):
        try:
            document = await document_collection.find_one({
                "_id": ObjectId(document_id),
                "user_id": current_user.id
            })
        except Exception as e:
            logger.warning(f"Erreur lors de la conversion en ObjectId: {e}")
    
    # Essai 3: Si le document n'est toujours pas trouvé, essayer avec une forme normalisée (sans tirets)
    if not document and "-" in document_id:
        normalized_id = document_id.replace("-", "")
        document = await document_collection.find_one({
            "_id": normalized_id,
            "user_id": current_user.id
        })
    
    # Essai 4: Rechercher par ID original dans les métadonnées
    if not document:
        logger.info(f"Document non trouvé avec ID direct: {document_id}, recherche par ID original dans les métadonnées")
        document = await document_collection.find_one({
            "metadata.properties.original_id": document_id,
            "user_id": current_user.id
        })
    
    # Essai 5: Rechercher dans tous les documents de l'utilisateur
    if not document:
        logger.info(f"Document non trouvé avec ID original, recherche dans tous les documents de l'utilisateur")
        cursor = document_collection.find({"user_id": current_user.id})
        async for doc in cursor:
            # Vérifier si l'ID correspond
            if str(doc.get("_id")) == document_id:
                document = doc
                break
            # Vérifier aussi dans les métadonnées
            if doc.get('metadata', {}).get('properties', {}).get('original_id') == document_id:
                document = doc
                break
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document non trouvé"
        )
    
    # Utiliser l'ID réel du document pour la suppression
    real_id = document.get("_id")
    logger.info(f"Document trouvé, suppression avec ID réel: {real_id}")
    
    # Supprimer le document de MongoDB
    await document_collection.delete_one({"_id": real_id})

    # Supprimer les chunks et embeddings associés dans Milvus
    try:
        # S'assurer que la connexion à Milvus est établie
        connected = await milvus_utils.connect_to_milvus()
        if connected:
            # Récupérer la collection Milvus
            collection = await milvus_utils.get_collection(config.MILVUS_COLLECTION)
            if collection:
                # Créer l'expression de filtre pour supprimer les chunks du document
                expr = f"document_id == '{str(real_id)}'"
                logger.info(f"Suppression des chunks dans Milvus avec filtre: {expr}")
                
                # Exécuter la suppression
                collection.delete(expr)
                logger.info(f"Chunks du document {real_id} supprimés de Milvus avec succès")
            else:
                logger.warning(f"Collection Milvus non disponible, impossible de supprimer les chunks du document {real_id}")
        else:
            logger.warning(f"Connexion à Milvus non établie, impossible de supprimer les chunks du document {real_id}")
    except Exception as e:
        # Ne pas échouer si la suppression des chunks échoue
        logger.error(f"Erreur lors de la suppression des chunks dans Milvus: {str(e)}")

@router.get("/{document_id}/chunks", response_model=List[DocumentChunkResponse])
async def get_document_chunks(
    document_id: str,
    current_user: UserInDB = Depends(get_current_active_user),
    chunking_strategy: ChunkingStrategy = Query(ChunkingStrategy.FIXED_SIZE),
    chunk_size: int = Query(config.DEFAULT_CHUNK_SIZE),
    chunk_overlap: int = Query(config.DEFAULT_CHUNK_OVERLAP)
) -> Any:
    """
    Récupérer les chunks d'un document.
    """
    document_collection = await get_document_collection()
    
    # Essayer différentes formes d'ID (ObjectId ou chaîne)
    document = None
    
    # Essai 1: Recherche directe par ID (sans conversion)
    document = await document_collection.find_one({
        "_id": document_id,
        "user_id": current_user.id
    })
    
    # Essai 2: Si ObjectId est valide, essayer avec ObjectId
    if not document and ObjectId.is_valid(document_id):
        try:
            document = await document_collection.find_one({
                "_id": ObjectId(document_id),
                "user_id": current_user.id
            })
        except Exception as e:
            logger.warning(f"Erreur lors de la conversion en ObjectId: {e}")
    
    # Essai 3: Si le document n'est toujours pas trouvé, essayer avec une forme normalisée (sans tirets)
    if not document and "-" in document_id:
        normalized_id = document_id.replace("-", "")
        document = await document_collection.find_one({
            "_id": normalized_id,
            "user_id": current_user.id
        })
    
    # Essai 4: Rechercher par ID original dans les métadonnées
    if not document:
        logger.info(f"Document non trouvé avec ID direct: {document_id}, recherche par ID original dans les métadonnées")
        document = await document_collection.find_one({
            "metadata.properties.original_id": document_id,
            "user_id": current_user.id
        })
    
    # Essai 5: Rechercher dans tous les documents de l'utilisateur
    if not document:
        logger.info(f"Document non trouvé avec ID original, recherche dans tous les documents de l'utilisateur")
        cursor = document_collection.find({"user_id": current_user.id})
        async for doc in cursor:
            # Vérifier si l'ID correspond
            if str(doc.get("_id")) == document_id:
                document = doc
                break
            # Vérifier aussi dans les métadonnées
            if doc.get('metadata', {}).get('properties', {}).get('original_id') == document_id:
                document = doc
                break
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document non trouvé"
        )
    
    # Utiliser le processeur de document directement au lieu du chunker
    from app.core.document_processor import process_text_to_chunks
    
    # Générer les chunks
    chunks = await process_text_to_chunks(
        document["content"],
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        chunking_method=chunking_strategy.value
    )
    
    # Formater les résultats
    result = []
    for i, chunk in enumerate(chunks):
        result.append({
            "id": f"{document_id}_chunk_{i}",
            "document_id": document_id,
            "chunk_index": i,
            "content": chunk.page_content,
            "metadata": {
                "start": chunk.metadata.get("start", 0),
                "end": chunk.metadata.get("end", 0),
                "strategy": chunking_strategy
            }
        })
    
    return result

@router.post("/{document_id}/process", response_model=ProcessingResponse)
async def process_document_endpoint(
    document_id: str,
    processing_request: ProcessingRequest,
    background_tasks: BackgroundTasks,
    current_user: UserInDB = Depends(get_current_active_user)
) -> Any:
    """
    Traite un document existant pour le chunking et l'embedding.
    
    Permet de spécifier des configurations personnalisées pour le chunking et l'embedding.
    """
    document_collection = await get_document_collection()
    
    # Vérifier que le document existe et appartient à l'utilisateur
    # Essayer d'abord avec l'ID direct
    document = await document_collection.find_one({
        "_id": document_id,
        "user_id": current_user.id
    })
    
    # Si non trouvé, essayer avec l'ID original dans les métadonnées
    if not document:
        logger.info(f"Document non trouvé avec ID direct: {document_id}, recherche par ID original dans les métadonnées")
        document = await document_collection.find_one({
            "metadata.properties.original_id": document_id,
            "user_id": current_user.id
        })
    
    # Si toujours non trouvé, essayer de convertir en ObjectId
    if not document:
        try:
            obj_id = ObjectId(document_id)
            document = await document_collection.find_one({
                "_id": obj_id,
                "user_id": current_user.id
            })
        except:
            pass
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document non trouvé"
        )
    
    # Vérifier que le document n'est pas déjà en cours de traitement
    if document["status"] == ProcessingStatus.PROCESSING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le document est déjà en cours de traitement"
        )
    
    # Récupérer l'ID réel du document pour la mise à jour
    real_id = document["_id"]
    
    # Mettre à jour le statut du document
    await document_collection.update_one(
        {"_id": real_id},
        {
            "$set": {
                "status": ProcessingStatus.PROCESSING,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    # Configurer le traitement
    chunking_config = processing_request.chunking_config or ChunkingConfig()
    embedding_config = processing_request.embedding_config or EmbeddingConfig()
    
    # Lancer le traitement en arrière-plan
    if document["type"] == DocumentType.URL and document.get("url"):
        # Pour les URLs
        background_tasks.add_task(
            process_url,
            url=document["url"],
            user_id=current_user.id,
            metadata=document.get("metadata", {}),
            chunking_config=chunking_config,
            embedding_config=embedding_config
        )
    else:
        # Pour les documents uploadés, nous avons besoin du contenu
        # Si le contenu n'est pas disponible, c'est une erreur
        if not document.get("content"):
            await document_collection.update_one(
                {"_id": real_id},
                {
                    "$set": {
                        "status": ProcessingStatus.FAILED,
                        "updated_at": datetime.utcnow(),
                        "metadata.properties.error": "Contenu du document non disponible"
                    }
                }
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Contenu du document non disponible pour le traitement"
            )
        
        # Sauvegarder le contenu dans un fichier temporaire
        temp_file_path = os.path.join(config.TEMP_DIR, f"{str(real_id)}.txt")
        async with aiofiles.open(temp_file_path, 'w', encoding='utf-8') as f:
            await f.write(document["content"])
        
        # Lancer le traitement
        background_tasks.add_task(
            process_document,
            file_path=temp_file_path,
            user_id=current_user.id,
            document_name=document.get("title"),
            metadata=document.get("metadata", {}),
            chunking_config=chunking_config,
            embedding_config=embedding_config,
            document_id=str(real_id)
        )
    
    return {
        "document_id": str(real_id),
        "status": ProcessingStatus.PROCESSING,
        "message": "Traitement du document lancé avec succès",
        "chunks_count": None,
        "error": None
    }

@router.post("/ingest", response_model=IngestionResponse)
async def ingest_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    params: Optional[str] = Form(None),
    run_async: bool = Form(False),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    Télécharge et traite un document en utilisant l'orchestrateur d'ingestion.
    
    Cette route offre des options avancées pour l'ingestion de documents,
    permettant de configurer finement le processus d'ingestion.
    
    Args:
        file: Fichier à télécharger et traiter
        params: Paramètres d'ingestion au format JSON (optionnel)
        run_async: Exécuter en arrière-plan si True
        current_user: Utilisateur connecté
    
    Returns:
        Informations sur le traitement du document
    """
    try:
        # Parser les paramètres s'ils sont fournis
        import json
        ingestion_params = IngestionParams()
        if params:
            params_dict = json.loads(params)
            ingestion_params = IngestionParams(**params_dict)
        
        # Enregistrer le fichier temporairement
        temp_file_path = ""
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_file:
            temp_file_path = temp_file.name
            content = await file.read()
            temp_file.write(content)
        
        # Générer un ID de tâche et un ID de document
        task_id = str(uuid.uuid4())
        document_id = str(uuid.uuid4())
        
        # Déterminer le type du document
        file_extension = os.path.splitext(file.filename)[1].lower()
        if file_extension in ['.txt', '.md', '.html', '.htm', '.json', '.csv']:
            doc_type = DocumentType.TEXT
        elif file_extension in ['.pdf']:
            doc_type = DocumentType.PDF
        elif file_extension in ['.jpg', '.jpeg', '.png', '.gif']:
            doc_type = DocumentType.IMAGE
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Type de fichier non pris en charge"
            )
        
        # Créer les métadonnées
        metadata = {
            "original_filename": file.filename,
            "file_extension": file_extension,
            "file_size": len(content),
            "collection_name": ingestion_params.collection_name or f"user_{current_user.id}_docs"
        }
        
        # Fonction de traitement asynchrone
        async def process_file(file_path, task_id, document_id):
            try:
                # Mettre à jour l'état de la tâche
                TASKS[task_id] = {
                    "status": "processing",
                    "document_id": document_id,
                    "start_time": datetime.now()
                }
                
                # Créer l'orchestrateur d'ingestion
                orchestrator = IngestionOrchestrator()
                
                # Traiter le document
                result = await orchestrator.process_document(
                    source=file_path,
                    document_type=doc_type,
                    user_id=current_user.id,
                    document_id=document_id,
                    metadata=metadata,
                    chunking_strategy=ingestion_params.chunker_type,
                    chunk_size=ingestion_params.chunk_size,
                    chunk_overlap=ingestion_params.chunk_overlap,
                    embedding_model=ingestion_params.embedding_type,
                    vector_store=ingestion_params.store_type,
                    collection_name=ingestion_params.collection_name or f"user_{current_user.id}_docs"
                )
                
                # Mettre à jour l'état de la tâche
                TASKS[task_id] = {
                    **TASKS[task_id],
                    "document_id": result.get("document_id", document_id),
                    "status": result.get("status", "error"),
                    "num_pages": result.get("num_documents", 0),
                    "num_chunks": result.get("num_chunks", 0),
                    "processing_time": result.get("processing_time_seconds", 0),
                    "error": result.get("error"),
                    "end_time": datetime.now()
                }
                
                # Supprimer le fichier temporaire
                try:
                    os.unlink(file_path)
                except Exception as e:
                    logger.warning(f"Erreur lors de la suppression du fichier temporaire: {str(e)}")
                
            except Exception as e:
                # En cas d'erreur
                TASKS[task_id] = {
                    **TASKS[task_id],
                    "status": "error",
                    "error": str(e),
                    "end_time": datetime.now()
                }
                
                # Supprimer le fichier temporaire
                try:
                    os.unlink(file_path)
                except Exception as e:
                    logger.warning(f"Erreur lors de la suppression du fichier temporaire: {str(e)}")
        
        # Exécuter de manière synchrone ou asynchrone
        if run_async:
            # Exécuter en arrière-plan
            background_tasks.add_task(process_file, temp_file_path, task_id, document_id)
            
            return IngestionResponse(
                document_id=document_id,
                task_id=task_id,
                status="pending",
                source=file.filename
            )
        else:
            # Exécuter de manière synchrone
            orchestrator = IngestionOrchestrator()
            result = await orchestrator.process_document(
                source=temp_file_path,
                document_type=doc_type,
                user_id=current_user.id,
                document_id=document_id,
                metadata=metadata,
                chunking_strategy=ingestion_params.chunker_type,
                chunk_size=ingestion_params.chunk_size,
                chunk_overlap=ingestion_params.chunk_overlap,
                embedding_model=ingestion_params.embedding_type,
                vector_store=ingestion_params.store_type,
                collection_name=ingestion_params.collection_name or f"user_{current_user.id}_docs"
            )
            
            # Supprimer le fichier temporaire
            try:
                os.unlink(temp_file_path)
            except Exception as e:
                logger.warning(f"Erreur lors de la suppression du fichier temporaire: {str(e)}")
            
            # Créer la réponse
            response = IngestionResponse(
                document_id=result.get("document_id", document_id),
                status=result.get("status", "error"),
                source=file.filename,
                num_pages=result.get("num_documents", 0),
                num_chunks=result.get("num_chunks", 0),
                processing_time=result.get("processing_time_seconds", 0),
                error=result.get("error")
            )
            
            return response
            
    except Exception as e:
        logger.error(f"Erreur lors du traitement du document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur lors du traitement du document: {str(e)}")

@router.get("/ingest/status/{task_id}", response_model=IngestionResponse)
async def get_ingestion_status(
    task_id: str,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    Récupère le statut d'une tâche d'ingestion.
    
    Args:
        task_id: ID de la tâche à vérifier
        current_user: Utilisateur connecté
    
    Returns:
        Informations sur l'état de la tâche
    """
    if task_id not in TASKS:
        raise HTTPException(status_code=404, detail="Tâche non trouvée")
    
    task = TASKS[task_id]
    
    # Calculer le temps de traitement si disponible
    processing_time = None
    if "start_time" in task and "end_time" in task:
        processing_time = (task["end_time"] - task["start_time"]).total_seconds()
    
    # Convertir en réponse
    return IngestionResponse(
        document_id=task.get("document_id", ""),
        task_id=task_id,
        status=task.get("status", "unknown"),
        source=task.get("source", ""),
        num_pages=task.get("num_pages"),
        num_chunks=task.get("num_chunks"),
        processing_time=processing_time or task.get("processing_time"),
        error=task.get("error")
    )