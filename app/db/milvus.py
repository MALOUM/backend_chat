from pymilvus import connections, Collection, utility
from pymilvus import CollectionSchema, FieldSchema, DataType
import logging
from app import config

logger = logging.getLogger(__name__)

# Variable globale pour la collection Milvus
collection = None

async def connect_to_milvus():
    """Établir la connexion à Milvus"""
    try:
        # Utiliser la configuration compatible avec la version de Milvus
        connections.connect(
            alias="default",
            host=config.MILVUS_HOST,
            port=config.MILVUS_PORT,
            user=config.MILVUS_USER,
            password=config.MILVUS_PASSWORD,
            secure=False,
            timeout=10
        )
        
        logger.info("Connexion à Milvus établie")
        
        # Vérifier la disponibilité de Milvus
        available = utility.is_connection_healthy("default")
        if available:
            logger.info("Milvus est disponible")
        else:
            logger.warning("Milvus n'est pas disponible")
    except Exception as e:
        logger.error(f"Erreur de connexion à Milvus: {e}")
        # Ne pas lever l'exception pour permettre à l'application de démarrer
        # même si Milvus n'est pas disponible
        logger.warning("L'application démarrera sans Milvus disponible")

async def close_milvus_connection():
    """Fermer la connexion à Milvus"""
    try:
        if collection:
            collection.release()
        connections.disconnect("default")
        logger.info("Connexion à Milvus fermée")
    except Exception as e:
        logger.error(f"Erreur lors de la fermeture de la connexion à Milvus: {e}")

async def create_milvus_collection():
    """Créer la collection Milvus avec le schéma approprié"""
    global collection
    
    # Définir les champs de la collection
    id_field = FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=100, is_primary=True)
    document_id_field = FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=100)
    chunk_id_field = FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=100)
    content_field = FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=8192)
    embedding_field = FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=config.EMBEDDING_DIMENSION)
    
    # Créer le schéma et la collection
    schema = CollectionSchema(fields=[id_field, document_id_field, chunk_id_field, content_field, embedding_field],
                             description="Collection de vecteurs d'embeddings pour RAG")
    
    collection = Collection(name=config.MILVUS_COLLECTION, schema=schema)
    
    # Créer un index pour rechercher par similarité
    index_params = {
        "metric_type": "COSINE",
        "index_type": "HNSW",
        "params": {"M": 8, "efConstruction": 64}
    }
    collection.create_index(field_name="embedding", index_params=index_params)
    collection.load()
    
    logger.info(f"Collection Milvus '{config.MILVUS_COLLECTION}' créée et indexée")

async def search_similar_documents(query_vector, limit=config.TOP_K_RETRIEVAL):
    """Rechercher des documents similaires dans Milvus"""
    if not collection:
        await connect_to_milvus()
    
    search_params = {"metric_type": "COSINE", "params": {"ef": 64}}
    results = collection.search(
        data=[query_vector],
        anns_field="embedding",
        param=search_params,
        limit=limit,
        output_fields=["document_id", "chunk_id", "content"]
    )
    
    return results

async def insert_embeddings(embeddings_data):
    """Insérer des embeddings dans Milvus"""
    if not collection:
        await connect_to_milvus()
    
    collection.insert(embeddings_data)
    logger.info(f"Inséré {len(embeddings_data['id'])} embeddings dans Milvus")
