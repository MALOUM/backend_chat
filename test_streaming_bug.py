#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import sys
import os
import json
from datetime import datetime
import logging
import requests

# Configuration du logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
API_URL = "http://localhost:8000"
EMAIL = "test3@example.com"  # Utilisateur existant
PASSWORD = "testpassword"

def login(email, password):
    """Se connecter et obtenir un token d'authentification"""
    try:
        response = requests.post(f"{API_URL}/api/auth/login", json={
            "email": email, 
            "password": password
        })
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Échec de connexion: {response.status_code}, {response.text}")
            return None
    except Exception as e:
        logger.error(f"Erreur lors de la connexion: {e}")
        return None

def create_session(token, session_title):
    """Créer une nouvelle session de chat"""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.post(f"{API_URL}/api/chat/sessions", headers=headers, json={
            "title": session_title
        })
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Échec de création de session: {response.status_code}, {response.text}")
            return None
    except Exception as e:
        logger.error(f"Erreur lors de la création de session: {e}")
        return None

async def test_streaming():
    """Tester la fonction de streaming en reproduisant le bug"""
    # 1. Se connecter pour obtenir un token
    logger.info("Connexion à l'API...")
    login_result = login(EMAIL, PASSWORD)
    if not login_result:
        logger.error("Échec de connexion")
        return
    
    token = login_result["access_token"]
    logger.info("Connexion réussie, token obtenu")
    
    # 2. Créer une session de test
    session_title = f"Test Streaming Bug {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    logger.info(f"Création d'une session: {session_title}")
    session = create_session(token, session_title)
    if not session:
        logger.error("Échec de création de session")
        return
    
    session_id = session["id"]
    logger.info(f"Session créée avec ID: {session_id}")
    
    # 3. Test direct de l'endpoint de streaming
    # Le problème se manifeste lors de l'utilisation de 'async for' dans le backend
    try:
        # Appel direct de l'API de streaming - c'est ici que le bug se produit dans le backend
        # Le backend tente d'utiliser 'async for' sur un objet coroutine, ce qui échoue
        headers = {"Authorization": f"Bearer {token}"}
        params = {
            "session_id": session_id,
            "message": "Explique-moi le fonctionnement de l'asynchronisme en Python et comment fonctionnent les coroutines.",
            "rag_enabled": "false"  # Désactiver RAG pour simplifier
        }
        
        logger.info("Envoi d'un message de test au streaming API...")
        logger.info(f"URL: {API_URL}/api/chat/stream, Params: {params}")
        
        # Ceci est juste pour montrer l'API call, mais l'erreur se produit côté serveur
        # quand il essaie de traiter cette requête
        response = requests.get(f"{API_URL}/api/chat/stream", headers=headers, params=params, stream=True)
        
        if response.status_code == 200:
            logger.info("Connexion au stream établie, réception des événements...")
            # Dans un cas normal, on lirait les événements SSE ici
            # Mais le serveur va probablement échouer avant d'en envoyer
            for line in response.iter_lines():
                if line:
                    decoded = line.decode('utf-8')
                    logger.info(f"Événement reçu: {decoded}")
        else:
            logger.error(f"Échec de connexion au stream: {response.status_code}, {response.text}")
    
    except Exception as e:
        logger.error(f"Erreur pendant le test de streaming: {e}")
    
    logger.info("Test terminé. Vérifiez les logs du serveur pour voir l'erreur 'async for requires object with __aiter__'")

if __name__ == "__main__":
    asyncio.run(test_streaming()) 