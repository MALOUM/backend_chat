"""
Script pour déboguer la structure des collections MongoDB dans l'application.
Ce script doit être placé dans le dossier app/ du conteneur pour avoir accès aux configurations et modèles.
"""
import asyncio
import logging
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
import json

# Configuration pour éviter les erreurs lors de la sérialisation de types complexes
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        if hasattr(obj, "__str__"):
            return str(obj)
        return super().default(obj)

async def inspect_db():
    # Connexion MongoDB
    client = AsyncIOMotorClient('mongodb://mongodb:27017')
    db = client['llm_rag_app']
    
    # Examiner la structure des sessions
    session_collection = db['chat_sessions']
    print("\n=== STRUCTURE DES SESSIONS ===")
    sessions = await session_collection.find().to_list(length=3)
    
    if not sessions:
        print("Aucune session trouvée!")
    else:
        for i, session in enumerate(sessions):
            print(f"\nSession {i+1}:")
            print(json.dumps(session, indent=2, cls=CustomJSONEncoder))
            
            # Vérifier si la session a un champ 'id' en plus de '_id'
            if 'id' in session and session['id'] != str(session['_id']):
                print(f"ATTENTION: La session a un champ 'id' différent de '_id'!")
                print(f"_id: {session['_id']}, id: {session['id']}")
    
    # Vérifier le nom de la base de données et des collections
    print("\n=== BASES DE DONNÉES ===")
    db_names = await client.list_database_names()
    print("Bases de données disponibles:", db_names)
    
    print("\n=== COLLECTIONS ===")
    collections = await db.list_collection_names()
    print("Collections dans la base de données:", collections)
    
    # Vérifier l'URL MongoDB configurée dans l'environnement
    print("\n=== CONFIGURATION ===")
    try:
        import os
        from app import config
        print(f"MONGODB_URL configurée: {config.MONGODB_URL}")
        print(f"MONGODB_DB_NAME configurée: {config.MONGODB_DB_NAME}")
        print(f"Variables d'environnement: MONGODB_URL={os.environ.get('MONGODB_URL')}")
    except ImportError:
        print("Impossible d'importer la configuration de l'application")
    
    # Essayer de rechercher une session spécifique (la première trouvée)
    if sessions:
        first_session = sessions[0]
        session_id = str(first_session["_id"])
        
        print(f"\n=== TEST DE RECHERCHE DE SESSION PAR ID ===")
        print(f"Recherche de session avec ID: {session_id}")
        
        # Recherche par ObjectId
        session_by_objectid = await session_collection.find_one({"_id": ObjectId(session_id)})
        print(f"Recherche par ObjectId: {'Trouvée' if session_by_objectid else 'Non trouvée'}")
        
        # Recherche par chaîne
        session_by_string = await session_collection.find_one({"_id": session_id})
        print(f"Recherche par chaîne: {'Trouvée' if session_by_string else 'Non trouvée'}")
        
        # Recherche par champ 'id'
        session_by_id_field = await session_collection.find_one({"id": session_id})
        print(f"Recherche par champ 'id': {'Trouvée' if session_by_id_field else 'Non trouvée'}")

async def main():
    print("=== INSPECTION DE LA BASE DE DONNÉES MONGODB ===")
    try:
        await inspect_db()
    except Exception as e:
        print(f"Erreur lors de l'inspection de la base de données: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 