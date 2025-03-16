import asyncio
import sys
import os
import json
from datetime import datetime
from bson import ObjectId
import requests
from pprint import pprint

# Ajouter le répertoire parent au chemin pour pouvoir importer les modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.chat_memory import ChatMemoryManager, count_tokens
from app.db.mongodb import get_message_collection, get_chat_session_collection, connect_to_mongo, close_mongo_connection
from app.models.chat import MessageRole

# Configuration
API_URL = "http://localhost:8000"
EMAIL = "test3@example.com"  # Utilisateur existant
PASSWORD = "testpassword"

async def create_test_session_with_many_messages():
    """Crée une session de test avec beaucoup de messages pour tester la limite de tokens"""
    # Créer une session directement dans MongoDB
    await connect_to_mongo()
    
    session_collection = await get_chat_session_collection()
    
    # Créer une nouvelle session
    session_id = str(ObjectId())
    user_id = "test_user_id"  # ID utilisateur fictif pour les tests
    
    session_data = {
        "_id": session_id,
        "user_id": user_id,
        "title": "Test de ConversationTokenBufferMemory",
        "rag_enabled": True,
        "rag_strategy": None,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "metadata": {}
    }
    
    await session_collection.insert_one(session_data)
    
    print(f"Session créée avec ID: {session_id}")
    
    # Ajouter beaucoup de messages pour dépasser le seuil de tokens
    message_collection = await get_message_collection()
    
    # Texte long pour simuler une conversation étendue
    long_text = """
    L'intelligence artificielle (IA) est un domaine de l'informatique qui vise à créer des machines capables de simuler l'intelligence humaine. 
    Elle englobe plusieurs sous-domaines, notamment l'apprentissage automatique, le traitement du langage naturel, la vision par ordinateur, 
    la robotique et bien d'autres. L'IA a connu une croissance exponentielle ces dernières années, en grande partie grâce aux avancées 
    dans le domaine de l'apprentissage profond (deep learning).

    L'apprentissage automatique (machine learning) est une branche de l'IA qui permet aux ordinateurs d'apprendre à partir de données 
    sans être explicitement programmés. Les algorithmes d'apprentissage automatique peuvent être supervisés, non supervisés ou par renforcement. 
    Dans l'apprentissage supervisé, le modèle est entraîné sur des données étiquetées, tandis que dans l'apprentissage non supervisé, 
    il doit découvrir des structures dans des données non étiquetées. L'apprentissage par renforcement, quant à lui, implique un agent 
    qui apprend à prendre des décisions en interagissant avec un environnement pour maximiser une récompense.

    Le traitement du langage naturel (NLP) est un domaine de l'IA qui se concentre sur l'interaction entre les ordinateurs et le langage humain. 
    Il comprend des tâches telles que la compréhension du langage, la génération de texte, la traduction automatique et l'analyse de sentiment. 
    Les modèles de langage de grande taille (LLM), comme GPT, BERT et LLaMA, ont révolutionné ce domaine en permettant une compréhension 
    et une génération de texte plus naturelles et contextuelles.

    La vision par ordinateur est un autre domaine important de l'IA qui permet aux machines d'interpréter et de comprendre des informations visuelles. 
    Elle est utilisée dans diverses applications, notamment la reconnaissance faciale, la détection d'objets, la conduite autonome et l'imagerie médicale. 
    Les réseaux de neurones convolutifs (CNN) ont été particulièrement efficaces pour résoudre des problèmes de vision par ordinateur.

    L'IA générative est un sous-domaine en plein essor qui se concentre sur la création de contenu nouveau et original, comme des images, 
    de la musique, du texte ou même du code. Des modèles comme DALL-E, Midjourney et Stable Diffusion ont démontré des capacités impressionnantes 
    à générer des images à partir de descriptions textuelles, tandis que des modèles comme ChatGPT peuvent générer du texte cohérent et contextuel.

    L'éthique de l'IA est devenue une préoccupation majeure à mesure que ces technologies se généralisent. Des questions sur la vie privée, 
    les biais algorithmiques, la transparence, la responsabilité et l'impact sur l'emploi sont au cœur des discussions. Il est crucial de développer 
    des cadres éthiques et réglementaires pour garantir que l'IA est développée et déployée de manière responsable et bénéfique pour l'humanité.

    L'avenir de l'IA promet des avancées encore plus significatives, avec des recherches en cours sur l'IA générale (AGI), 
    qui vise à créer des systèmes capables de comprendre, apprendre et appliquer des connaissances dans différents domaines, 
    similaires à l'intelligence humaine. Bien que nous soyons encore loin de l'AGI, les progrès actuels dans des domaines comme 
    l'apprentissage auto-supervisé, l'apprentissage par renforcement et les architectures neuronales avancées nous rapprochent de cet objectif.
    """
    
    # Créer une série de messages pour simuler une longue conversation
    messages = []
    for i in range(40):  # Augmenter à 40 paires pour dépasser clairement le seuil
        # Message utilisateur
        user_message = {
            "_id": str(ObjectId()),
            "session_id": session_id,
            "role": MessageRole.USER,
            "content": f"Question {i+1}: {long_text[:200]}... (suite de la question {i+1})",
            "timestamp": datetime.utcnow()
        }
        messages.append(user_message)
        
        # Réponse assistant
        assistant_message = {
            "_id": str(ObjectId()),
            "session_id": session_id,
            "role": MessageRole.ASSISTANT,
            "content": f"Réponse {i+1}: {long_text[200:400]}... (suite de la réponse {i+1})",
            "timestamp": datetime.utcnow()
        }
        messages.append(assistant_message)
    
    # Insérer tous les messages
    await message_collection.insert_many(messages)
    print(f"Ajout de {len(messages)} messages à la session")
    
    return session_id, user_id

async def test_token_buffer_memory():
    """Teste la fonctionnalité de ConversationTokenBufferMemory"""
    # Créer une session avec beaucoup de messages
    session_id, user_id = await create_test_session_with_many_messages()
    
    if not session_id or not user_id:
        print("Impossible de créer la session de test")
        return
    
    # Récupérer tous les messages de la session
    message_collection = await get_message_collection()
    all_messages = []
    cursor = message_collection.find({"session_id": session_id}).sort("timestamp", 1)
    async for msg in cursor:
        all_messages.append(msg)
    
    # Calculer le nombre total de tokens pour tous les messages
    all_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in all_messages])
    total_tokens = count_tokens(all_text)
    print(f"Nombre total de tokens dans la session: {total_tokens}")
    
    # Créer une instance de ChatMemoryManager
    memory_manager = ChatMemoryManager(session_id, user_id)
    
    # Récupérer l'historique avec limite de tokens
    limited_history = await memory_manager.get_chat_history()
    
    # Calculer le nombre de tokens dans l'historique limité
    limited_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in limited_history])
    limited_tokens = count_tokens(limited_text)
    print(f"Nombre de tokens dans l'historique limité: {limited_tokens}")
    
    # Vérifier si l'historique a été limité
    if limited_tokens < total_tokens:
        print(f"L'historique a été limité! Réduction de {total_tokens - limited_tokens} tokens ({((total_tokens - limited_tokens) / total_tokens) * 100:.2f}%)")
    else:
        print("L'historique n'a pas été limité. Le seuil de tokens n'a peut-être pas été dépassé.")
    
    # Afficher le nombre de messages conservés
    print(f"Nombre total de messages: {len(all_messages)}")
    print(f"Nombre de messages conservés: {len(limited_history)}")
    
    # Afficher les premiers et derniers messages conservés
    if limited_history:
        print("\nPremier message conservé:")
        print(f"{limited_history[0]['role']}: {limited_history[0]['content'][:100]}...")
        
        print("\nDernier message conservé:")
        print(f"{limited_history[-1]['role']}: {limited_history[-1]['content'][:100]}...")

async def main():
    """Fonction principale"""
    print("Test de la fonctionnalité ConversationTokenBufferMemory...")
    try:
        await test_token_buffer_memory()
    finally:
        await close_mongo_connection()
    print("Test terminé.")

if __name__ == "__main__":
    asyncio.run(main()) 