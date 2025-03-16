import streamlit as st
import requests
import json
import time
import threading
import sseclient
import os
import queue
import urllib.parse
import pymongo
import bson
from bson.objectid import ObjectId

# Configuration de l'application
API_URL = "http://localhost:8000/api"
MONGODB_URL = "mongodb://localhost:27017"
MONGODB_DB_NAME = "llm_rag_app"
st.set_page_config(page_title="Test d'Annulation du Streaming et Vérification des IDs", layout="wide")

# Fonctions d'API
def login(email, password):
    """Se connecter à l'API"""
    try:
        response = requests.post(
            f"{API_URL}/auth/login",
            json={"email": email, "password": password}
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            return None
    except Exception as e:
        st.sidebar.error(f"Exception lors de la connexion: {str(e)}")
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
            return response.json()
        else:
            st.sidebar.error(f"Erreur lors de la création de la session: {response.text}")
            return None
    except Exception as e:
        st.sidebar.error(f"Exception lors de la création de la session: {str(e)}")
        return None

def get_session(token, session_id):
    """Récupérer une session spécifique"""
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(
            f"{API_URL}/chat/sessions/{session_id}",
            headers=headers
        )
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Erreur lors de la récupération de la session: {response.text}")
            return None
    except Exception as e:
        st.error(f"Exception lors de la récupération de la session: {str(e)}")
        return None

def get_sessions(token):
    """Récupérer la liste des sessions de chat"""
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(
            f"{API_URL}/chat/sessions",
            headers=headers
        )
        if response.status_code == 200:
            return response.json()
        else:
            st.sidebar.error(f"Erreur lors de la récupération des sessions: {response.text}")
            return []
    except Exception as e:
        st.sidebar.error(f"Exception lors de la récupération des sessions: {str(e)}")
        return []

def create_message(token, session_id, content):
    """Créer un nouveau message dans une session"""
    headers = {"Authorization": f"Bearer {token}"}
    data = {"role": "user", "content": content}
    
    try:
        response = requests.post(
            f"{API_URL}/chat/sessions/{session_id}/messages",
            headers=headers,
            json=data
        )
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Erreur lors de la création du message: {response.text}")
            return None
    except Exception as e:
        st.error(f"Exception lors de la création du message: {str(e)}")
        return None

def get_messages(token, session_id):
    """Récupérer les messages d'une session"""
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(
            f"{API_URL}/chat/sessions/{session_id}/messages",
            headers=headers
        )
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Erreur lors de la récupération des messages: {response.text}")
            return []
    except Exception as e:
        st.error(f"Exception lors de la récupération des messages: {str(e)}")
        return []

def create_feedback(token, message_id, rating="good", category="relevance", comment="Test feedback"):
    """Créer un feedback pour un message"""
    headers = {"Authorization": f"Bearer {token}"}
    data = {
        "message_id": message_id,
        "rating": rating,
        "category": category,
        "comment": comment
    }
    
    try:
        response = requests.post(
            f"{API_URL}/feedback",
            headers=headers,
            json=data
        )
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Erreur lors de la création du feedback: {response.text}")
            return None
    except Exception as e:
        st.error(f"Exception lors de la création du feedback: {str(e)}")
        return None

def get_feedback(token, message_id):
    """Récupérer le feedback pour un message spécifique"""
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(
            f"{API_URL}/feedback/message/{message_id}",
            headers=headers
        )
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Erreur lors de la récupération du feedback: {response.text}")
            return None
    except Exception as e:
        st.error(f"Exception lors de la récupération du feedback: {str(e)}")
        return None

def get_feedbacks(token):
    """Récupérer tous les feedbacks de l'utilisateur"""
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(
            f"{API_URL}/feedback",
            headers=headers
        )
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Erreur lors de la récupération des feedbacks: {response.text}")
            return []
    except Exception as e:
        st.error(f"Exception lors de la récupération des feedbacks: {str(e)}")
        return []

def cancel_streaming(token, message_id):
    """Annuler une génération en cours"""
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.post(
            f"{API_URL}/chat/cancel/{message_id}",
            headers=headers
        )
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Erreur lors de l'annulation: {response.text}")
            return None
    except Exception as e:
        st.error(f"Exception lors de l'annulation: {str(e)}")
        return None

# Fonctions MongoDB
def get_mongodb_connection():
    """Établir une connexion à MongoDB"""
    try:
        client = pymongo.MongoClient(MONGODB_URL)
        db = client[MONGODB_DB_NAME]
        return db
    except Exception as e:
        st.error(f"Erreur de connexion à MongoDB: {str(e)}")
        return None

def check_id_in_mongodb(collection_name, object_id):
    """Vérifier si un ID existe dans MongoDB"""
    try:
        db = get_mongodb_connection()
        if not db:
            return None
        
        collection = db[collection_name]
        
        # Essayer d'abord avec l'ID tel quel
        result = collection.find_one({"_id": object_id})
        
        # Si non trouvé, essayer avec ObjectId
        if not result and ObjectId.is_valid(object_id):
            result = collection.find_one({"_id": ObjectId(object_id)})
            
        return result
    except Exception as e:
        st.error(f"Erreur lors de la vérification de l'ID dans MongoDB: {str(e)}")
        return None

def verify_id_consistency(api_id, collection_name):
    """Vérifier la cohérence entre l'ID de l'API et celui de MongoDB"""
    mongodb_obj = check_id_in_mongodb(collection_name, api_id)
    
    if mongodb_obj:
        mongodb_id = str(mongodb_obj["_id"])
        return {
            "api_id": api_id,
            "mongodb_id": mongodb_id,
            "match": api_id == mongodb_id,
            "mongodb_object": mongodb_obj
        }
    else:
        return {
            "api_id": api_id,
            "mongodb_id": None,
            "match": False,
            "mongodb_object": None
        }

# Initialiser les variables de session
if 'token' not in st.session_state:
    st.session_state.token = ""
if 'current_session' not in st.session_state:
    st.session_state.current_session = None
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'streaming_active' not in st.session_state:
    st.session_state.streaming_active = False
if 'current_message_id' not in st.session_state:
    st.session_state.current_message_id = None
if 'id_verifications' not in st.session_state:
    st.session_state.id_verifications = []

# Fonction pour ajouter un message au chat
def add_message(role, content):
    st.session_state.messages.append({"role": role, "content": content})

# Fonction pour gérer le streaming de la réponse
def handle_streaming(session_id, message):
    headers = {"Authorization": f"Bearer {st.session_state.token}"}
    
    # Ajouter un message temporaire pour l'assistant
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        message_placeholder.markdown("⏳ Génération en cours...")
    
    # Ajouter un bouton d'arrêt
    stop_col = st.container()
    
    with stop_col:
        if st.button("🛑 Arrêter la génération", key="stop_button"):
            if st.session_state.current_message_id:
                result = cancel_streaming(st.session_state.token, st.session_state.current_message_id)
                if result:
                    st.success("Génération annulée avec succès")
                    # Mettre à jour le message avec l'indication d'annulation
                    buffer = st.session_state.messages[-1]["content"] + " [GÉNÉRATION ANNULÉE]"
                    st.session_state.messages[-1]["content"] = buffer
                    message_placeholder.markdown(buffer)
                    st.session_state.streaming_active = False
                    return
    
    try:
        # Encoder le message pour l'URL
        encoded_message = urllib.parse.quote(message)
        
        # Faire la requête de streaming
        response = requests.get(
            f"{API_URL}/chat/stream?session_id={session_id}&message={encoded_message}&rag_enabled=false",
            headers=headers,
            stream=True
        )
        
        client = sseclient.SSEClient(response)
        
        buffer = ""
        st.session_state.streaming_active = True
        
        # Ajouter un message vide pour l'assistant
        add_message("assistant", "")
        
        for event in client.events():
            if event.event == "message":
                data = json.loads(event.data)
                token_text = data.get("token", "")
                
                # Si c'est le premier token, récupérer l'ID du message
                if st.session_state.current_message_id is None and "message_id" in data:
                    st.session_state.current_message_id = data["message_id"]
                
                # Si on a reçu [CANCELLED], afficher le message d'annulation
                if token_text == "[CANCELLED]":
                    buffer += " [GÉNÉRATION ANNULÉE]"
                    st.session_state.messages[-1]["content"] = buffer
                    message_placeholder.markdown(buffer)
                    break
                
                buffer += token_text
                st.session_state.messages[-1]["content"] = buffer
                message_placeholder.markdown(buffer)
                
            elif event.event == "cancelled":
                buffer += " [GÉNÉRATION ANNULÉE]"
                st.session_state.messages[-1]["content"] = buffer
                message_placeholder.markdown(buffer)
                break
                
            elif event.event == "error":
                data = json.loads(event.data)
                error_msg = data.get("error", "Erreur inconnue")
                st.error(f"Erreur de streaming: {error_msg}")
                break
                
            elif event.event == "done":
                data = json.loads(event.data)
                if "message_id" in data:
                    # Vérifier la cohérence de l'ID du message de réponse
                    message_id = data["message_id"]
                    verification = verify_id_consistency(message_id, "messages")
                    st.session_state.id_verifications.append({
                        "type": "Message (réponse)",
                        "verification": verification,
                        "timestamp": time.time()
                    })
                break
                
    except Exception as e:
        st.error(f"Exception lors du streaming: {str(e)}")
    
    # Indiquer que le streaming est terminé
    st.session_state.streaming_active = False
    st.session_state.current_message_id = None
    
    # Supprimer le bouton d'arrêt
    stop_col.empty()

# Fonction pour tester la cohérence des IDs
def test_id_consistency():
    if not st.session_state.token:
        st.error("Vous devez être connecté pour effectuer ce test")
        return
    
    with st.spinner("Test en cours..."):
        # 1. Créer une session
        session = create_session(st.session_state.token, f"Test ID Consistency {time.time()}")
        if not session:
            st.error("Échec de la création de session")
            return
        
        session_id = session["id"]
        st.info(f"Session créée avec l'ID: {session_id}")
        
        # 2. Récupérer la session par son ID
        retrieved_session = get_session(st.session_state.token, session_id)
        if not retrieved_session:
            st.error("Échec de la récupération de la session")
            return
        
        retrieved_session_id = retrieved_session["id"]
        st.info(f"Session récupérée avec l'ID: {retrieved_session_id}")
        
        # Vérifier la cohérence de l'ID de session
        session_match = session_id == retrieved_session_id
        st.session_state.id_verifications.append({
            "type": "Session",
            "creation_id": session_id,
            "retrieval_id": retrieved_session_id,
            "match": session_match,
            "timestamp": time.time()
        })
        
        # 3. Créer un message
        message = create_message(st.session_state.token, session_id, "Test de cohérence des IDs")
        if not message:
            st.error("Échec de la création de message")
            return
        
        message_id = message["id"]
        st.info(f"Message créé avec l'ID: {message_id}")
        
        # 4. Récupérer les messages de la session
        messages = get_messages(st.session_state.token, session_id)
        if not messages:
            st.error("Échec de la récupération des messages")
            return
        
        # Trouver le message que nous venons de créer
        retrieved_message = None
        for msg in messages:
            if msg["content"] == "Test de cohérence des IDs":
                retrieved_message = msg
                break
        
        if not retrieved_message:
            st.error("Message créé non trouvé dans la liste des messages")
            return
        
        retrieved_message_id = retrieved_message["id"]
        st.info(f"Message récupéré avec l'ID: {retrieved_message_id}")
        
        # Vérifier la cohérence de l'ID de message
        message_match = message_id == retrieved_message_id
        st.session_state.id_verifications.append({
            "type": "Message",
            "creation_id": message_id,
            "retrieval_id": retrieved_message_id,
            "match": message_match,
            "timestamp": time.time()
        })
        
        # 5. Créer un feedback
        feedback = create_feedback(st.session_state.token, message_id)
        if not feedback:
            st.error("Échec de la création de feedback")
            return
        
        feedback_id = feedback["id"]
        st.info(f"Feedback créé avec l'ID: {feedback_id}")
        
        # 6. Récupérer le feedback pour le message
        retrieved_feedback = get_feedback(st.session_state.token, message_id)
        if not retrieved_feedback:
            st.error("Échec de la récupération du feedback")
            return
        
        retrieved_feedback_id = retrieved_feedback["id"]
        st.info(f"Feedback récupéré avec l'ID: {retrieved_feedback_id}")
        
        # Vérifier la cohérence de l'ID de feedback
        feedback_match = feedback_id == retrieved_feedback_id
        st.session_state.id_verifications.append({
            "type": "Feedback",
            "creation_id": feedback_id,
            "retrieval_id": retrieved_feedback_id,
            "match": feedback_match,
            "timestamp": time.time()
        })
        
        # 7. Récupérer tous les feedbacks
        all_feedbacks = get_feedbacks(st.session_state.token)
        if not all_feedbacks:
            st.error("Échec de la récupération de tous les feedbacks")
            return
        
        # Trouver le feedback que nous venons de créer
        found_in_all = False
        for fb in all_feedbacks:
            if fb["id"] == feedback_id:
                found_in_all = True
                break
        
        st.session_state.id_verifications.append({
            "type": "Feedback (liste)",
            "creation_id": feedback_id,
            "retrieval_id": "Trouvé dans la liste" if found_in_all else "Non trouvé dans la liste",
            "match": found_in_all,
            "timestamp": time.time()
        })
        
        st.success("Test de cohérence des IDs terminé avec succès!")

# Interface utilisateur
st.title("🤖 Test d'Annulation du Streaming et Vérification des IDs")

# Onglets pour les différentes fonctionnalités
tab1, tab2 = st.tabs(["Test de Streaming", "Vérification des IDs"])

# Sidebar pour l'authentification et la gestion des sessions
with st.sidebar:
    st.header("1. Authentification")
    
    if not st.session_state.token:
        email = st.text_input("Email", value="test@example.com")
        password = st.text_input("Mot de passe", value="Password123!", type="password")
        
        if st.button("Se connecter"):
            result = login(email, password)
            if result:
                st.session_state.token = result["access_token"]
                st.success("Connexion réussie!")
                st.rerun()
    else:
        st.success("Connecté")
        st.code(f"Token: {st.session_state.token[:20]}...", language="bash")
        
        if st.button("Se déconnecter"):
            st.session_state.token = ""
            st.session_state.current_session = None
            st.session_state.messages = []
            st.rerun()
    
    if st.session_state.token:
        st.header("2. Gestion des Sessions")
        
        # Création de session
        st.subheader("Créer une nouvelle session")
        session_title = st.text_input("Titre de la session", value="Test Abort Streaming")
        
        if st.button("Créer une session"):
            session = create_session(st.session_state.token, session_title)
            if session:
                st.success(f"Session créée avec l'ID: {session['id']}")
                st.session_state.current_session = session
                st.session_state.messages = []
                
                # Vérifier la cohérence de l'ID de session
                session_verification = verify_id_consistency(session["id"], "chat_sessions")
                st.session_state.id_verifications.append({
                    "type": "Session (création)",
                    "verification": session_verification,
                    "timestamp": time.time()
                })
                
                st.rerun()
        
        # Sélection de session existante
        st.subheader("Ou sélectionner une session existante")
        
        if st.button("Rafraîchir les sessions"):
            st.session_state.sessions = get_sessions(st.session_state.token)
            st.rerun()
        
        sessions = get_sessions(st.session_state.token)
        
        if sessions:
            session_options = {f"{s['title']} (ID: {s['id']})": s for s in sessions}
            selected_session = st.selectbox("Sessions disponibles", options=list(session_options.keys()))
            
            if st.button("Sélectionner cette session"):
                st.session_state.current_session = session_options[selected_session]
                st.session_state.messages = []
                st.success(f"Session sélectionnée: {st.session_state.current_session['title']}")
                st.rerun()

# Onglet 1: Test de Streaming
with tab1:
    if st.session_state.token and st.session_state.current_session:
        st.subheader(f"Session active: {st.session_state.current_session['title']}")
        
        # Afficher l'historique des messages
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        
        # Zone de saisie du message
        if not st.session_state.streaming_active:
            if prompt := st.chat_input("Entrez votre message..."):
                # Afficher le message de l'utilisateur
                with st.chat_message("user"):
                    st.markdown(prompt)
                
                # Ajouter le message à l'historique
                add_message("user", prompt)
                
                # Créer un message dans la base de données
                user_message = create_message(
                    st.session_state.token, 
                    st.session_state.current_session['id'], 
                    prompt
                )
                
                if user_message:
                    # Vérifier la cohérence de l'ID du message utilisateur
                    message_verification = verify_id_consistency(user_message["id"], "messages")
                    st.session_state.id_verifications.append({
                        "type": "Message (utilisateur)",
                        "verification": message_verification,
                        "timestamp": time.time()
                    })
                
                # Lancer le streaming de la réponse
                handle_streaming(st.session_state.current_session['id'], prompt)
        else:
            st.info("Génération en cours... Utilisez le bouton d'arrêt pour annuler.")
    
    else:
        if not st.session_state.token:
            st.info("Veuillez vous connecter dans la barre latérale pour commencer.")
        elif not st.session_state.current_session:
            st.info("Veuillez créer ou sélectionner une session dans la barre latérale.")

# Onglet 2: Vérification des IDs
with tab2:
    st.subheader("Test de cohérence des IDs entre création et récupération")
    
    if st.button("Exécuter un test complet de cohérence des IDs"):
        test_id_consistency()
    
    st.subheader("Résultats des vérifications")
    
    if not st.session_state.id_verifications:
        st.info("Aucune vérification n'a encore été effectuée. Créez une session, envoyez des messages ou exécutez le test complet.")
    else:
        # Afficher les résultats des vérifications
        for i, verification in enumerate(reversed(st.session_state.id_verifications)):
            if "creation_id" in verification:
                # Nouveau format de vérification (création vs récupération)
                with st.expander(f"{verification['type']} - {time.strftime('%H:%M:%S', time.localtime(verification['timestamp']))} - {'✅ Correspondance' if verification['match'] else '❌ Différence'}"):
                    st.write(f"**ID à la création:** `{verification['creation_id']}`")
                    st.write(f"**ID à la récupération:** `{verification['retrieval_id']}`")
                    st.write(f"**Correspondance:** {'✅ Oui' if verification['match'] else '❌ Non'}")
            elif "verification" in verification:
                # Ancien format de vérification (API vs MongoDB)
                with st.expander(f"{verification['type']} - {time.strftime('%H:%M:%S', time.localtime(verification['timestamp']))} - {'✅ Correspondance' if verification['verification']['match'] else '❌ Différence'}"):
                    st.write(f"**ID API:** `{verification['verification']['api_id']}`")
                    st.write(f"**ID MongoDB:** `{verification['verification']['mongodb_id'] or 'Non trouvé'}`")
                    st.write(f"**Correspondance:** {'✅ Oui' if verification['verification']['match'] else '❌ Non'}")
                    
                    if verification['verification']['mongodb_object']:
                        with st.expander("Détails de l'objet MongoDB"):
                            # Afficher les détails de l'objet MongoDB
                            for key, value in verification['verification']['mongodb_object'].items():
                                if key == '_id':
                                    st.write(f"**{key}:** `{value}`")
                                else:
                                    st.write(f"**{key}:** `{value}`")

# Afficher les instructions
with st.expander("Instructions d'utilisation"):
    st.markdown("""
    ## Comment utiliser cet outil de test

    ### Onglet "Test de Streaming"
    1. **Authentification** : Connectez-vous avec vos identifiants dans la barre latérale
    2. **Session** : Créez une nouvelle session ou sélectionnez-en une existante dans la barre latérale
    3. **Chat** : 
       - Entrez votre message dans la zone de saisie en bas
       - La réponse s'affichera progressivement
       - Utilisez le bouton "Arrêter la génération" pour tester la fonctionnalité d'annulation
    
    ### Onglet "Vérification des IDs"
    1. **Test complet** : Cliquez sur "Exécuter un test complet de cohérence des IDs" pour créer une session, un message et un feedback, puis vérifier la cohérence des IDs
    2. **Résultats** : Consultez les résultats des vérifications effectuées, avec les détails des objets MongoDB
    
    **Note** : L'annulation est plus visible avec des requêtes qui génèrent des réponses longues.
    """)

# Footer
st.markdown("---")
st.caption("Test d'Annulation du Streaming et Vérification des IDs | Projet Backend Chat") 