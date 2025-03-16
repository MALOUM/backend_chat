import requests
import json
import time
import os
import datetime
import sys
from pymongo import MongoClient
from pprint import pprint

# Configuration
API_URL = "http://localhost:8000/api"
EMAIL = "test3@example.com"  # Utilisateur existant
PASSWORD = "testpassword"
MONGODB_URI = "mongodb://localhost:27017"
DB_NAME = "chat_db"

def get_mongodb_connection():
    """Établir une connexion à MongoDB"""
    try:
        client = MongoClient(MONGODB_URI)
        db = client[DB_NAME]
        print("Connexion à MongoDB établie")
        return db
    except Exception as e:
        print(f"Erreur de connexion à MongoDB: {str(e)}")
        return None

def login(email, password):
    """Se connecter à l'API"""
    try:
        response = requests.post(
            f"{API_URL}/auth/login",
            json={"email": email, "password": password}
        )
        
        if response.status_code == 200:
            print(f"Connexion réussie avec l'utilisateur {email}")
            return response.json()
        else:
            print(f"Erreur de connexion: {response.text}")
            return None
    except Exception as e:
        print(f"Exception lors de la connexion: {str(e)}")
        return None

def create_session(token, session_title):
    """Créer une nouvelle session de chat"""
    headers = {"Authorization": f"Bearer {token}"}
    data = {"title": session_title, "rag_enabled": False}
    
    try:
        response = requests.post(
            f"{API_URL}/chat/sessions",
            headers=headers,
            json=data
        )
        if response.status_code == 200:
            print(f"Session créée: {session_title}")
            return response.json()
        else:
            print(f"Erreur lors de la création de la session: {response.text}")
            return None
    except Exception as e:
        print(f"Exception lors de la création de la session: {str(e)}")
        return None

def create_message(token, session_id, content, role="user"):
    """Créer un message dans la session"""
    headers = {"Authorization": f"Bearer {token}"}
    data = {"content": content, "role": role}
    
    try:
        response = requests.post(
            f"{API_URL}/chat/sessions/{session_id}/messages",
            headers=headers,
            json=data
        )
        
        if response.status_code == 200:
            print(f"Message créé: {content[:50]}...")
            return response.json()
        else:
            print(f"Erreur lors de la création du message: {response.text}")
            return None
    except Exception as e:
        print(f"Exception lors de la création du message: {str(e)}")
        return None

def check_for_assistant_response(db, session_id, last_message_id, max_tries=30, delay=1):
    """Vérifier l'apparition d'une réponse de l'assistant dans la base de données"""
    collection = db.messages
    tries = 0
    
    print("Attente de la réponse de l'assistant...")
    
    while tries < max_tries:
        # Chercher un message de l'assistant après le dernier message utilisateur
        pipeline = [
            {"$match": {"session_id": session_id, "role": "assistant"}},
            {"$sort": {"timestamp": -1}},
            {"$limit": 1}
        ]
        
        results = list(collection.aggregate(pipeline))
        
        if results and len(results) > 0:
            assistant_message = results[0]
            print(f"Réponse de l'assistant trouvée (longueur: {len(assistant_message['content'])} caractères)")
            return assistant_message
        
        time.sleep(delay)
        tries += 1
        if tries % 5 == 0:
            print(f"Toujours en attente... ({tries}/{max_tries})")
    
    print("Aucune réponse de l'assistant trouvée après plusieurs tentatives")
    return None

def check_token_count(db, session_id):
    """Vérifier le nombre total de tokens dans la session"""
    collection = db.summaries
    
    # Chercher un résumé pour cette session
    summary = collection.find_one({"session_id": session_id})
    
    if summary:
        print(f"Résumé trouvé pour la session:")
        print(f"  - Tokens avant résumé: {summary.get('tokens_before', 'N/A')}")
        print(f"  - Tokens après résumé: {summary.get('tokens_after', 'N/A')}")
        print(f"  - Réduction: {summary.get('tokens_before', 0) - summary.get('tokens_after', 0)} tokens")
        print(f"  - Contenu du résumé: {summary.get('content', '')[:200]}...")
        return True
    else:
        print("Aucun résumé généré pour cette session")
        return False

def test_conversation_memory():
    """Tester la mémoire des conversations"""
    # 1. Connexion à MongoDB
    db = get_mongodb_connection()
    if not db:
        print("Échec de la connexion à MongoDB")
        return
    
    # 2. Se connecter à l'API
    login_result = login(EMAIL, PASSWORD)
    if not login_result:
        print("Échec de la connexion")
        return
    
    token = login_result["access_token"]
    
    # 3. Créer une session
    session_title = f"Test Direct Memory {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    session = create_session(token, session_title)
    if not session:
        print("Échec de la création de session")
        return
    
    session_id = session["id"]
    print(f"Session créée avec l'ID: {session_id}")
    
    # 4. Première question
    question1 = "Quels sont les trois principes fondamentaux de l'intelligence artificielle ?"
    message1 = create_message(token, session_id, question1)
    if not message1:
        print("Échec de la création du premier message")
        return
    
    # 5. Attendre la réponse à la première question
    response1 = check_for_assistant_response(db, session_id, message1["id"])
    if not response1:
        print("Échec de la première question")
        return
    
    print("\n--- Première question complétée ---\n")
    time.sleep(2)  # Attente entre les questions
    
    # 6. Seconde question liée à la première
    question2 = "Peux-tu me donner plus de détails sur le deuxième principe que tu as mentionné ?"
    message2 = create_message(token, session_id, question2)
    if not message2:
        print("Échec de la création du second message")
        return
    
    # 7. Attendre la réponse à la seconde question
    response2 = check_for_assistant_response(db, session_id, message2["id"])
    if not response2:
        print("Échec de la seconde question")
        return
    
    print("\n--- Seconde question complétée ---\n")
    
    # 8. Vérifier le comptage de tokens et la génération de résumé
    has_summary = check_token_count(db, session_id)
    
    # 9. Afficher un résumé
    print("\n===== RÉSUMÉ DU TEST =====")
    print(f"Session: {session_title}")
    print(f"Question 1: {question1}")
    print(f"Réponse 1 (extrait): {response1['content'][:300]}...")
    print(f"Question 2: {question2}")
    print(f"Réponse 2 (extrait): {response2['content'][:300]}...")
    print(f"Résumé généré: {'Oui' if has_summary else 'Non'}")
    print("==========================")
    
    # 10. Vérifier que la réponse à la deuxième question fait référence à la première
    print("\nTest terminé. Vérifiez manuellement que la réponse à la deuxième question")
    print("fait bien référence au contenu de la première réponse.")

if __name__ == "__main__":
    test_conversation_memory() 