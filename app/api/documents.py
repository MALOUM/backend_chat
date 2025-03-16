from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks, File, UploadFile, Form, Query
from typing import List, Optional, Any
from datetime import datetime
import uuid
import json
import os
import aiofiles
from pydantic import HttpUrl

from app.dependencies import get_current_active_user
from app.models.user import UserInDB
from app.models.document import Document, DocumentType, ProcessingStatus, DocumentMetadata
from app.schemas.document import (
    DocumentCreate, DocumentUpdate, DocumentResponse,
    DocumentChunkResponse, ChunkingStrategy
)
from app.db.mongodb import get_document_collection
from app.core.document_processor import process_document, process_url, extract_text_from_upload
from app.rag.chunkers import get_chunker
from app import config

router = APIRouter(prefix="/documents", tags=["Documents"])

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
    
    # Préparer le document
    new_document = Document(
        _id=document_id,
        user_id=current_user._id,
        title=document_data.title,
        type=document_data.type,
        content=document_data.content or "",
        url=str(document_data.url) if document_data.url else None,
        status=ProcessingStatus.PENDING,
        metadata=DocumentMetadata(**(document_data.metadata or {})),
        created_at=now,
        updated_at=now
    )
    
    await document_collection.insert_one(new_document.dict(by_alias=True))
    
    # Traitement asynchrone du document
    if document_data.type == DocumentType.URL:
        background_tasks.add_task(
            process_url,
            document_id=document_id,
            url=str(document_data.url)
        )
    else:
        background_tasks.add_task(
            process_document,
            document_id=document_id
        )
    
    return {
        "id": document_id,
        "user_id": current_user._id,
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
    current_user: UserInDB = Depends(get_current_active_user)
) -> Any:
    """
    Télécharger et traiter un fichier document.
    """
    document_collection = await get_document_collection()
    
    document_id = str(uuid.uuid4())
    now = datetime.utcnow()
    
    # Déterminer le type du document
    file_extension = os.path.splitext(file.filename)[1].lower()
    if file_extension in ['.txt', '.md', '.html', '.htm', '.json', '.csv']:
        doc_type = DocumentType.TEXT
    elif file_extension in ['.pdf']:
        doc_type = DocumentType.PDF
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
            parsed_metadata = DocumentMetadata(**metadata_dict)
        except json.JSONDecodeError:
            pass
    
    new_document = Document(
        _id=document_id,
        user_id=current_user._id,
        title=title or file.filename,
        type=doc_type,
        content=text_content,
        status=ProcessingStatus.PENDING,
        metadata=parsed_metadata,
        created_at=now,
        updated_at=now
    )
    
    await document_collection.insert_one(new_document.dict(by_alias=True))
    
    # Traitement asynchrone du document
    background_tasks.add_task(
        process_document,
        document_id=document_id
    )
    
    # Supprimer le fichier temporaire
    os.remove(temp_file_path)
    
    return {
        "id": document_id,
        "user_id": current_user._id,
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
        {"user_id": current_user._id}
    ).sort("created_at", -1).skip(skip).limit(limit)
    
    async for doc in cursor:
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
    
    document = await document_collection.find_one({
        "_id": document_id,
        "user_id": current_user._id
    })
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document non trouvé"
        )
        
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
    
    document = await document_collection.find_one({
        "_id": document_id,
        "user_id": current_user._id
    })
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document non trouvé"
        )
    
    update_data = {k: v for k, v in document_data.dict(exclude_unset=True).items() if v is not None}
    
    if update_data:
        update_data["updated_at"] = datetime.utcnow()
        update_data["status"] = ProcessingStatus.PENDING
        
        await document_collection.update_one(
            {"_id": document_id},
            {"$set": update_data}
        )
        
        # Re-traiter le document si le contenu a changé
        if "content" in update_data:
            background_tasks.add_task(
                process_document,
                document_id=document_id
            )
    
    updated_document = await document_collection.find_one({"_id": document_id})
    
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
    
    document = await document_collection.find_one({
        "_id": document_id,
        "user_id": current_user._id
    })
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document non trouvé"
        )
    
    await document_collection.delete_one({"_id": document_id})

    # TODO: Supprimer aussi les chunks et embeddings associés

@router.get("/{document_id}/chunks", response_model=List[DocumentChunkResponse])
async def get_document_chunks(
    document_id: str,
    current_user: UserInDB = Depends(get_current_active_user),
    chunking_strategy: ChunkingStrategy = Query(ChunkingStrategy.FIXED_SIZE),
    chunk_size: int = Query(config.DEFAULT_CHUNK_SIZE),
    chunk_overlap: int = Query(config.DEFAULT_CHUNK_OVERLAP)
) -> Any:
    """
    Récupérer ou générer les chunks d'un document avec une stratégie spécifique.
    """
    document_collection = await get_document_collection()
    
    document = await document_collection.find_one({
        "_id": document_id,
        "user_id": current_user._id
    })
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document non trouvé"
        )
    
    # Obtenir le chunker approprié
    chunker = await get_chunker(chunking_strategy.value)
    
    # Générer les chunks
    chunks = await chunker.chunk_text(
        document["content"],
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )
    
    # Formater les résultats
    result = []
    for i, chunk in enumerate(chunks):
        result.append({
            "id": f"{document_id}_chunk_{i}",
            "document_id": document_id,
            "chunk_index": i,
            "content": chunk.text,
            "metadata": {
                "start": chunk.metadata.get("start", 0),
                "end": chunk.metadata.get("end", 0),
                "strategy": chunking_strategy
            }
        })
    
    return result