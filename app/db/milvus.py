from pymilvus import connections, Collection, utility
from pymilvus import CollectionSchema, FieldSchema, DataType
import logging
import uuid
from typing import List, Dict, Any, Optional
import numpy as np
import asyncio

# Imports LangChain
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.embeddings import Embeddings

from app import config

logger = logging.getLogger(__name__)

# Variables globales pour la gestion de Milvus
_connection_established = False
_collection_cache = {}
embedding_model = None

def get_connection_params():
    """Récupère les paramètres de connexion à Milvus depuis la configuration."""
    return {
        "host": config.MILVUS_HOST,
        "port": config.MILVUS_PORT,
        "user": config.MILVUS_USER,
        "password": config.MILVUS_PASSWORD,
        "secure": False,
        "timeout": 30  # Augmentation du timeout pour gérer les environnements plus lents
    }

async def connect_to_milvus(alias: str = "default", retry_count: int = 3, retry_delay: int = 2):
    """
    Établit une connexion à Milvus avec mécanisme de réessai.
    
    Args:
        alias: Alias de la connexion
        retry_count: Nombre de tentatives en cas d'échec
        retry_delay: Délai entre les tentatives (en secondes)
        
    Returns:
        True si la connexion est établie avec succès, False sinon
    """
    global _connection_established
    
    # Si déjà connecté, retourner simplement True
    if _connection_established and connections.has_connection(alias):
        return True
    
    for attempt in range(retry_count):
        try:
            params = get_connection_params()
            # Déconnexion préalable si une connexion existe déjà
            if connections.has_connection(alias):
                try:
                    connections.disconnect(alias)
                    logger.debug(f"Connexion existante fermée (alias: {alias})")
                except Exception as e:
                    logger.warning(f"Erreur lors de la déconnexion de {alias}: {e}")
            
            # Établir la connexion
            connections.connect(alias=alias, **params)
            
            # Vérifier la disponibilité de Milvus
            if hasattr(utility, 'is_connection_healthy'):
                available = utility.is_connection_healthy(alias)
            else:
                available = connections.has_connection(alias)
                
            if available:
                logger.info(f"Connexion à Milvus établie (alias: {alias})")
                _connection_established = True
                return True
            else:
                logger.warning(f"Connexion à Milvus établie mais non disponible (alias: {alias})")
                
                if attempt < retry_count - 1:
                    logger.info(f"Nouvelle tentative dans {retry_delay} secondes (tentative {attempt+1}/{retry_count})")
                    await asyncio.sleep(retry_delay)
                    continue
                return False
                
        except Exception as e:
            logger.warning(f"Erreur lors de la connexion à Milvus (tentative {attempt+1}/{retry_count}): {e}")
            
            if attempt < retry_count - 1:
                logger.info(f"Nouvelle tentative dans {retry_delay} secondes")
                await asyncio.sleep(retry_delay)
            else:
                logger.error(f"Impossible d'établir une connexion à Milvus après {retry_count} tentatives")
                return False
    
    return False

async def close_milvus_connection(alias: str = "default"):
    """
    Ferme la connexion à Milvus.
    
    Args:
        alias: Alias de la connexion à fermer
    """
    global _connection_established
    
    try:
        # Libérer les collections en cache
        for collection_name, collection in _collection_cache.items():
            try:
                collection.release()
                logger.debug(f"Collection '{collection_name}' libérée")
            except Exception as e:
                logger.warning(f"Erreur lors de la libération de la collection '{collection_name}': {e}")
        
        # Vider le cache
        _collection_cache.clear()
        
        # Fermer la connexion
        if connections.has_connection(alias):
            connections.disconnect(alias)
            logger.info(f"Connexion à Milvus fermée (alias: {alias})")
        
        _connection_established = False
    except Exception as e:
        logger.error(f"Erreur lors de la fermeture de la connexion à Milvus: {e}")

async def get_collection(collection_name: str, create_if_missing: bool = False, dimension: int = None):
    """
    Récupère une collection Milvus, la crée si nécessaire.
    
    Args:
        collection_name: Nom de la collection
        create_if_missing: Si True, crée la collection si elle n'existe pas
        dimension: Dimension des vecteurs (obligatoire si create_if_missing=True)
        
    Returns:
        Collection Milvus ou None en cas d'erreur
    """
    # Vérifier si la collection est en cache
    if collection_name in _collection_cache:
        return _collection_cache[collection_name]
    
    # S'assurer que la connexion est établie
    if not _connection_established:
        connected = await connect_to_milvus()
        if not connected:
            logger.error(f"Impossible de se connecter à Milvus pour récupérer la collection '{collection_name}'")
            return None
    
    try:
        # Vérifier si la collection existe
        if utility.has_collection(collection_name):
            collection = Collection(name=collection_name)
            collection.load()
            _collection_cache[collection_name] = collection
            logger.info(f"Collection '{collection_name}' chargée")
            return collection
        elif create_if_missing and dimension is not None:
            # Créer la collection
            collection = await create_collection(collection_name, dimension)
            if collection:
                _collection_cache[collection_name] = collection
            return collection
        else:
            logger.warning(f"Collection '{collection_name}' non trouvée")
            return None
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de la collection '{collection_name}': {e}")
        return None

async def create_collection(collection_name: str, dimension: int):
    """
    Crée une nouvelle collection Milvus.
    
    Args:
        collection_name: Nom de la collection
        dimension: Dimension des vecteurs d'embedding
        
    Returns:
        Collection créée ou None en cas d'erreur
    """
    try:
        # Définir les champs de la collection
        id_field = FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=100, is_primary=True)
        document_id_field = FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=100)
        chunk_id_field = FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=100)
        content_field = FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=8192)
        embedding_field = FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dimension)
        
        # Créer le schéma et la collection
        schema = CollectionSchema(
            fields=[id_field, document_id_field, chunk_id_field, content_field, embedding_field],
            description="Collection de vecteurs d'embeddings pour RAG"
        )
        
        collection = Collection(name=collection_name, schema=schema)
        
        # Créer un index pour rechercher par similarité
        index_params = {
            "metric_type": "L2",
            "index_type": "HNSW",
            "params": {"M": 8, "efConstruction": 64}
        }
        collection.create_index(field_name="embedding", index_params=index_params)
        collection.load()
        
        logger.info(f"Collection '{collection_name}' créée et indexée")
        return collection
    except Exception as e:
        logger.error(f"Erreur lors de la création de la collection '{collection_name}': {e}")
        return None

def get_embedding_model(model_name: Optional[str] = None) -> Embeddings:
    """
    Obtient ou initialise le modèle d'embedding.
    
    Args:
        model_name: Nom du modèle d'embedding (optionnel, utilise la configuration par défaut si non spécifié)
        
    Returns:
        Modèle d'embedding initialisé
    """
    global embedding_model
    
    if embedding_model is None or model_name:
        model_to_use = model_name or config.EMBEDDING_MODEL
        
        logger.info(f"Initialisation du modèle d'embedding: {model_to_use}")
        embedding_model = HuggingFaceEmbeddings(
            model_name=model_to_use,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True}
        )
    
    return embedding_model

async def search_similar_documents(query_vector, limit=config.TOP_K_RETRIEVAL, collection_name=None):
    """Rechercher des documents similaires dans Milvus"""
    collection_to_use = collection_name or config.MILVUS_COLLECTION
    
    # Obtenir la collection
    collection = await get_collection(collection_to_use)
    
    if not collection:
        logger.error(f"Impossible de rechercher dans Milvus: collection '{collection_to_use}' non disponible")
        return []
    
    search_params = {"metric_type": "L2", "params": {"ef": 64}}
    try:
        results = collection.search(
            data=[query_vector],
            anns_field="embedding",
            param=search_params,
            limit=limit,
            output_fields=["document_id", "chunk_id", "content"]
        )
        
        return results
    except Exception as e:
        logger.error(f"Erreur lors de la recherche dans Milvus: {e}")
        
        # Essayer de reconnecter et réessayer une fois
        connected = await connect_to_milvus(retry_count=1)
        if connected:
            try:
                # Récupérer à nouveau la collection et réessayer
                collection = await get_collection(collection_to_use)
                if collection:
                    results = collection.search(
                        data=[query_vector],
                        anns_field="embedding",
                        param=search_params,
                        limit=limit,
                        output_fields=["document_id", "chunk_id", "content"]
                    )
                    return results
            except Exception as e2:
                logger.error(f"Erreur lors de la seconde tentative de recherche dans Milvus: {e2}")
        
        return []

async def insert_embeddings(embeddings_data: Dict[str, Any]) -> List[str]:
    """
    Génère des embeddings pour les textes fournis et les insère dans Milvus.
    
    Args:
        embeddings_data: Dictionnaire contenant:
            - texts: Liste des textes à encoder
            - metadatas: Liste des métadonnées associées à chaque texte
            - model: Nom du modèle d'embedding (optionnel)
            - collection: Nom de la collection Milvus à utiliser (optionnel)
            - dimension: Dimension des embeddings (optionnel)
        
    Returns:
        Liste des IDs d'embedding générés
    """
    texts = embeddings_data.get("texts", [])
    metadatas = embeddings_data.get("metadatas", [])
    model_name = embeddings_data.get("model", config.EMBEDDING_MODEL)
    collection_name = embeddings_data.get("collection", config.MILVUS_COLLECTION)
    dimension = embeddings_data.get("dimension", config.EMBEDDING_DIMENSION)
    
    if not texts:
        logger.warning("Aucun texte fourni pour créer des embeddings")
        return []
    
    # Obtenir le modèle d'embedding
    model = get_embedding_model(model_name)
    
    # Générer les embeddings
    logger.info(f"Génération de {len(texts)} embeddings avec le modèle {model_name}")
    try:
        embeddings = model.embed_documents(texts)
        
        # Préparer les données pour Milvus
        ids = [str(uuid.uuid4()) for _ in range(len(texts))]
        document_ids = [metadata.get("document_id", "") for metadata in metadatas]
        chunk_ids = [metadata.get("chunk_id", "") for metadata in metadatas]
        
        # Vérifier les dimensions
        embedding_dimension = len(embeddings[0])
        if embedding_dimension != dimension:
            logger.warning(f"Dimension des embeddings ({embedding_dimension}) différente de la configuration ({dimension})")
        
        # Obtenir ou créer la collection
        collection = await get_collection(collection_name, create_if_missing=True, dimension=embedding_dimension)
        
        if not collection:
            logger.error(f"Impossible d'insérer dans Milvus: collection '{collection_name}' non disponible")
            return []
        
        # Insérer dans Milvus
        insert_data = {
            "id": ids,
            "document_id": document_ids,
            "chunk_id": chunk_ids,
            "content": texts,
            "embedding": embeddings
        }
        
        collection.insert(insert_data)
        logger.info(f"Inséré {len(ids)} embeddings dans Milvus")
        
        return ids
    except Exception as e:
        logger.error(f"Erreur lors de la génération ou insertion des embeddings: {str(e)}")
        # Essayer de reconnecter et réessayer une fois
        connected = await connect_to_milvus(retry_count=1)
        if connected:
            try:
                # Regénérer les embeddings si nécessaire
                embeddings = model.embed_documents(texts)
                
                # Préparer les données pour Milvus
                ids = [str(uuid.uuid4()) for _ in range(len(texts))]
                document_ids = [metadata.get("document_id", "") for metadata in metadatas]
                chunk_ids = [metadata.get("chunk_id", "") for metadata in metadatas]
                
                # Insérer dans Milvus
                collection = await get_collection(collection_name, create_if_missing=True, dimension=len(embeddings[0]))
                if collection:
                    insert_data = {
                        "id": ids,
                        "document_id": document_ids,
                        "chunk_id": chunk_ids,
                        "content": texts,
                        "embedding": embeddings
                    }
                    
                    collection.insert(insert_data)
                    logger.info(f"Inséré {len(ids)} embeddings dans Milvus après reconnexion")
                    return ids
            except Exception as e2:
                logger.error(f"Erreur lors de la seconde tentative d'insertion des embeddings: {str(e2)}")
        
        return []

"""
Module utilitaire pour les opérations de base avec Milvus.
Ce module fournit des fonctions de bas niveau pour interagir avec Milvus.
Pour les opérations de plus haut niveau, utilisez app.ingestion_service.vector_store.milvus_store.MilvusStore.
"""

from pymilvus import connections, Collection, utility
from pymilvus import CollectionSchema, FieldSchema, DataType
import logging
from typing import Optional, Dict, Any, List

from app import config

logger = logging.getLogger(__name__)

# Variables globales pour la connexion Milvus
_connection_established = False
_collection_cache = {}

def get_connection_params():
    """Récupère les paramètres de connexion à Milvus depuis la configuration."""
    return {
        "host": config.MILVUS_HOST,
        "port": config.MILVUS_PORT,
        "user": config.MILVUS_USER,
        "password": config.MILVUS_PASSWORD,
        "secure": False,
        "timeout": 10
    }

async def connect_to_milvus(alias: str = "default"):
    """
    Établit une connexion à Milvus.
    
    Args:
        alias: Alias de la connexion
        
    Returns:
        True si la connexion est établie avec succès, False sinon
    """
    global _connection_established
    
    if _connection_established:
        return True
    
    try:
        params = get_connection_params()
        connections.connect(alias=alias, **params)
        
        # Vérifier la disponibilité de Milvus
        if hasattr(utility, 'is_connection_healthy'):
            available = utility.is_connection_healthy(alias)
        else:
            available = connections.has_connection(alias)
            
        if available:
            logger.info(f"Connexion à Milvus établie (alias: {alias})")
            _connection_established = True
            return True
        else:
            logger.warning(f"Connexion à Milvus établie mais non disponible (alias: {alias})")
            return False
            
    except Exception as e:
        logger.error(f"Erreur lors de la connexion à Milvus: {e}")
        return False

async def close_milvus_connection(alias: str = "default"):
    """
    Ferme la connexion à Milvus.
    
    Args:
        alias: Alias de la connexion à fermer
    """
    global _connection_established
    
    try:
        # Libérer les collections en cache
        for collection_name, collection in _collection_cache.items():
            try:
                collection.release()
                logger.debug(f"Collection '{collection_name}' libérée")
            except Exception as e:
                logger.warning(f"Erreur lors de la libération de la collection '{collection_name}': {e}")
        
        # Vider le cache
        _collection_cache.clear()
        
        # Fermer la connexion
        connections.disconnect(alias)
        _connection_established = False
        logger.info(f"Connexion à Milvus fermée (alias: {alias})")
    except Exception as e:
        logger.error(f"Erreur lors de la fermeture de la connexion à Milvus: {e}")

async def get_collection(collection_name: str, create_if_missing: bool = False, dimension: int = None):
    """
    Récupère une collection Milvus, la crée si nécessaire.
    
    Args:
        collection_name: Nom de la collection
        create_if_missing: Si True, crée la collection si elle n'existe pas
        dimension: Dimension des vecteurs (obligatoire si create_if_missing=True)
        
    Returns:
        Collection Milvus ou None en cas d'erreur
    """
    # Vérifier si la collection est en cache
    if collection_name in _collection_cache:
        return _collection_cache[collection_name]
    
    # S'assurer que la connexion est établie
    if not _connection_established:
        connected = await connect_to_milvus()
        if not connected:
            return None
    
    try:
        # Vérifier si la collection existe
        if utility.has_collection(collection_name):
            collection = Collection(name=collection_name)
            collection.load()
            _collection_cache[collection_name] = collection
            logger.info(f"Collection '{collection_name}' chargée")
            return collection
        elif create_if_missing and dimension:
            # Créer la collection
            collection = await create_collection(collection_name, dimension)
            _collection_cache[collection_name] = collection
            return collection
        else:
            logger.warning(f"Collection '{collection_name}' non trouvée")
            return None
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de la collection '{collection_name}': {e}")
        return None

async def create_collection(collection_name: str, dimension: int):
    """
    Crée une nouvelle collection Milvus.
    
    Args:
        collection_name: Nom de la collection
        dimension: Dimension des vecteurs d'embedding
        
    Returns:
        Collection créée ou None en cas d'erreur
    """
    try:
        # Définir les champs de la collection
        id_field = FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=100, is_primary=True)
        document_id_field = FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=100)
        chunk_id_field = FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=100)
        content_field = FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=8192)
        embedding_field = FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dimension)
        
        # Créer le schéma et la collection
        schema = CollectionSchema(
            fields=[id_field, document_id_field, chunk_id_field, content_field, embedding_field],
            description="Collection de vecteurs d'embeddings pour RAG"
        )
        
        collection = Collection(name=collection_name, schema=schema)
        
        # Créer un index pour rechercher par similarité
        index_params = {
            "metric_type": "L2",
            "index_type": "HNSW",
            "params": {"M": 8, "efConstruction": 64}
        }
        collection.create_index(field_name="embedding", index_params=index_params)
        collection.load()
        
        logger.info(f"Collection '{collection_name}' créée et indexée")
        return collection
    except Exception as e:
        logger.error(f"Erreur lors de la création de la collection '{collection_name}': {e}")
        return None
