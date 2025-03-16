from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from typing import Dict, Any, Optional
import logging
from app import config

logger = logging.getLogger(__name__)

# Variables globales pour la connexion et la base de données
client: Optional[AsyncIOMotorClient] = None
db: Optional[AsyncIOMotorDatabase] = None

async def connect_to_mongo():
    """Établir la connexion à MongoDB"""
    global client, db
    try:
        client = AsyncIOMotorClient(config.MONGODB_URL)
        db = client[config.MONGODB_DB_NAME]
        logger.info("Connexion à MongoDB établie")
        
        # Créer les index nécessaires
        await setup_indexes()
    except Exception as e:
        logger.error(f"Erreur de connexion à MongoDB: {e}")
        raise

async def close_mongo_connection():
    """Fermer la connexion à MongoDB"""
    global client
    if client:
        client.close()
        logger.info("Connexion à MongoDB fermée")

async def setup_indexes():
    """Configurer les index MongoDB pour les performances"""
    global db
    if db is not None:
        # Index pour les utilisateurs
        await db.users.create_index("email", unique=True)
        await db.users.create_index("username", unique=True)
        
        # Index pour les sessions de chat
        await db.chat_sessions.create_index("user_id")
        await db.chat_sessions.create_index("created_at")
        
        # Index pour les messages
        await db.messages.create_index("session_id")
        await db.messages.create_index("timestamp")
        
        # Index pour les documents
        await db.documents.create_index("user_id")
        await db.documents.create_index([("content", "text")])
        
        # Index pour les feedbacks
        await db.feedbacks.create_index("user_id")
        await db.feedbacks.create_index("message_id")
        await db.feedbacks.create_index("session_id")
        await db.feedbacks.create_index("timestamp")
        
        logger.info("Index MongoDB configurés")

async def get_db() -> AsyncIOMotorDatabase:
    """Récupérer l'instance de la base de données"""
    global db, client
    if db is None:
        await connect_to_mongo()
    return db

async def get_user_collection() -> AsyncIOMotorCollection:
    """Récupérer la collection des utilisateurs"""
    db = await get_db()
    return db.users

async def get_chat_session_collection() -> AsyncIOMotorCollection:
    """Récupérer la collection des sessions de chat"""
    db = await get_db()
    return db.chat_sessions

async def get_message_collection() -> AsyncIOMotorCollection:
    """Récupérer la collection des messages"""
    db = await get_db()
    return db.messages

async def get_document_collection() -> AsyncIOMotorCollection:
    """Récupérer la collection des documents"""
    db = await get_db()
    return db.documents

async def get_feedback_collection() -> AsyncIOMotorCollection:
    """Récupérer la collection des feedbacks utilisateurs"""
    db = await get_db()
    return db.feedbacks