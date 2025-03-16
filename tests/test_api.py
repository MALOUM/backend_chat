import requests
import json
import time
import uuid
from pprint import pprint

# Configuration
API_URL = "http://localhost:8000/api"
EMAIL = "test@example.com"
PASSWORD = "Password123!"
USERNAME = "testuser"

# Couleurs pour les logs
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def log_success(message):
    print(f"{Colors.OKGREEN}✓ {message}{Colors.ENDC}")

def log_error(message):
    print(f"{Colors.FAIL}✗ {message}{Colors.ENDC}")

def log_info(message):
    print(f"{Colors.OKBLUE}ℹ {message}{Colors.ENDC}")

def log_section(message):
    print(f"\n{Colors.HEADER}{Colors.BOLD}=== {message} ==={Colors.ENDC}")

# Fonctions d'API
def register_user():
    log_section("Test d'enregistrement d'utilisateur")
    try:
        response = requests.post(
            f"{API_URL}/auth/register",
            json={
                "email": EMAIL,
                "username": USERNAME,
                "password": PASSWORD
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            log_success(f"Utilisateur enregistré avec succès: {data}")
            return data["access_token"]
        else:
            log_error(f"Erreur lors de l'enregistrement: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        log_error(f"Exception lors de l'enregistrement: {str(e)}")
        return None

def login_user():
    log_section("Test de connexion utilisateur")
    try:
        response = requests.post(
            f"{API_URL}/auth/login",
            json={
                "email": EMAIL,
                "password": PASSWORD
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            log_success(f"Connexion réussie: {data}")
            return data["access_token"]
        else:
            log_error(f"Erreur lors de la connexion: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        log_error(f"Exception lors de la connexion: {str(e)}")
        return None

def create_session(token):
    log_section("Test de création de session")
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.post(
            f"{API_URL}/chat/sessions",
            headers=headers,
            json={
                "title": "Session de test",
                "rag_enabled": False
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            log_success(f"Session créée avec succès: {data}")
            return data
        else:
            log_error(f"Erreur lors de la création de session: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        log_error(f"Exception lors de la création de session: {str(e)}")
        return None

def get_sessions(token):
    log_section("Test de récupération des sessions")
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(
            f"{API_URL}/chat/sessions",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            log_success(f"Sessions récupérées avec succès: {len(data)} sessions")
            # Afficher les détails des sessions
            for i, session in enumerate(data):
                log_info(f"Session {i+1}: ID={session['id']}, Titre={session['title']}")
            return data
        else:
            log_error(f"Erreur lors de la récupération des sessions: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        log_error(f"Exception lors de la récupération des sessions: {str(e)}")
        return None

def get_session(token, session_id):
    log_section(f"Test de récupération de la session {session_id}")
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(
            f"{API_URL}/chat/sessions/{session_id}",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            log_success(f"Session récupérée avec succès: {data}")
            return data
        else:
            log_error(f"Erreur lors de la récupération de la session: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        log_error(f"Exception lors de la récupération de la session: {str(e)}")
        return None

def update_session(token, session_id):
    log_section(f"Test de mise à jour de la session {session_id}")
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.put(
            f"{API_URL}/chat/sessions/{session_id}",
            headers=headers,
            json={
                "title": "Session de test mise à jour",
                "rag_enabled": True
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            log_success(f"Session mise à jour avec succès: {data}")
            return data
        else:
            log_error(f"Erreur lors de la mise à jour de la session: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        log_error(f"Exception lors de la mise à jour de la session: {str(e)}")
        return None

def create_message(token, session_id):
    log_section(f"Test de création de message dans la session {session_id}")
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.post(
            f"{API_URL}/chat/sessions/{session_id}/messages",
            headers=headers,
            json={
                "content": "Bonjour, ceci est un message de test",
                "role": "user"
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            log_success(f"Message créé avec succès: {data}")
            return data
        else:
            log_error(f"Erreur lors de la création du message: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        log_error(f"Exception lors de la création du message: {str(e)}")
        return None

def get_messages(token, session_id):
    log_section(f"Test de récupération des messages de la session {session_id}")
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(
            f"{API_URL}/chat/sessions/{session_id}/messages",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            log_success(f"Messages récupérés avec succès: {len(data)} messages")
            # Afficher les détails des messages
            for i, message in enumerate(data):
                log_info(f"Message {i+1}: ID={message['id']}, Role={message['role']}, Contenu={message['content'][:30]}...")
            return data
        else:
            log_error(f"Erreur lors de la récupération des messages: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        log_error(f"Exception lors de la récupération des messages: {str(e)}")
        return None

def create_feedback(token, message_id):
    log_section(f"Test de création de feedback pour le message {message_id}")
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.post(
            f"{API_URL}/feedback",
            headers=headers,
            json={
                "message_id": message_id,
                "rating": "good",
                "category": "relevance",
                "comment": "Ceci est un feedback de test"
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            log_success(f"Feedback créé avec succès: {data}")
            return data
        else:
            log_error(f"Erreur lors de la création du feedback: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        log_error(f"Exception lors de la création du feedback: {str(e)}")
        return None

def get_feedbacks(token):
    log_section("Test de récupération des feedbacks")
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(
            f"{API_URL}/feedback",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            log_success(f"Feedbacks récupérés avec succès: {len(data)} feedbacks")
            # Afficher les détails des feedbacks
            for i, feedback in enumerate(data):
                log_info(f"Feedback {i+1}: ID={feedback['id']}, Message ID={feedback['message_id']}, Rating={feedback['rating']}")
            return data
        else:
            log_error(f"Erreur lors de la récupération des feedbacks: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        log_error(f"Exception lors de la récupération des feedbacks: {str(e)}")
        return None

def get_message_feedback(token, message_id):
    log_section(f"Test de récupération du feedback pour le message {message_id}")
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(
            f"{API_URL}/feedback/message/{message_id}",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            log_success(f"Feedback récupéré avec succès: {data}")
            # Afficher l'ID du feedback pour le débogage
            log_info(f"ID du feedback récupéré: {data['id']}")
            return data
        else:
            log_error(f"Erreur lors de la récupération du feedback: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        log_error(f"Exception lors de la récupération du feedback: {str(e)}")
        return None

def update_feedback(token, feedback_id):
    log_section(f"Test de mise à jour du feedback {feedback_id}")
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.put(
            f"{API_URL}/feedback/{feedback_id}",
            headers=headers,
            json={
                "rating": "very_good",
                "comment": "Feedback mis à jour"
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            log_success(f"Feedback mis à jour avec succès: {data}")
            return data
        else:
            log_error(f"Erreur lors de la mise à jour du feedback: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        log_error(f"Exception lors de la mise à jour du feedback: {str(e)}")
        return None

def get_session_feedbacks(token, session_id):
    log_section(f"Test de récupération des feedbacks pour la session {session_id}")
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(
            f"{API_URL}/feedback/session/{session_id}",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            log_success(f"Feedbacks de session récupérés avec succès: {len(data)} feedbacks")
            return data
        else:
            log_error(f"Erreur lors de la récupération des feedbacks de session: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        log_error(f"Exception lors de la récupération des feedbacks de session: {str(e)}")
        return None

def get_feedback_stats(token):
    log_section("Test de récupération des statistiques de feedback")
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(
            f"{API_URL}/feedback/stats",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            log_success(f"Statistiques récupérées avec succès: {data}")
            return data
        else:
            log_error(f"Erreur lors de la récupération des statistiques: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        log_error(f"Exception lors de la récupération des statistiques: {str(e)}")
        return None

def delete_feedback(token, feedback_id):
    log_section(f"Test de suppression du feedback {feedback_id}")
    try:
        headers = {"Authorization": f"Bearer {token}"}
        
        # Afficher des informations de débogage
        log_info(f"Tentative de suppression du feedback avec ID: {feedback_id}")
        log_info(f"Type de l'ID: {type(feedback_id)}")
        
        response = requests.delete(
            f"{API_URL}/feedback/{feedback_id}",
            headers=headers
        )
        
        if response.status_code == 204:
            log_success(f"Feedback supprimé avec succès")
            return True
        else:
            log_error(f"Erreur lors de la suppression du feedback: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        log_error(f"Exception lors de la suppression du feedback: {str(e)}")
        return False

def delete_session(token, session_id):
    log_section(f"Test de suppression de la session {session_id}")
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.delete(
            f"{API_URL}/chat/sessions/{session_id}",
            headers=headers
        )
        
        if response.status_code == 204:
            log_success(f"Session supprimée avec succès")
            return True
        else:
            log_error(f"Erreur lors de la suppression de la session: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        log_error(f"Exception lors de la suppression de la session: {str(e)}")
        return False

def test_streaming(token, session_id):
    log_section(f"Test de streaming pour la session {session_id}")
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(
            f"{API_URL}/chat/stream?session_id={session_id}&message=Bonjour, comment ça va?",
            headers=headers,
            stream=True
        )
        
        if response.status_code == 200:
            log_success(f"Connexion au streaming établie")
            
            # Lire quelques événements
            for i, line in enumerate(response.iter_lines()):
                if line:
                    decoded_line = line.decode('utf-8')
                    if decoded_line.startswith('data:'):
                        data = json.loads(decoded_line[5:])
                        log_info(f"Événement reçu: {data}")
                
                # Limiter à 5 événements pour le test
                if i >= 5:
                    break
                    
            return True
        else:
            log_error(f"Erreur lors de la connexion au streaming: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        log_error(f"Exception lors du test de streaming: {str(e)}")
        return False

def run_tests():
    log_section("DÉBUT DES TESTS")
    
    # Enregistrement et connexion
    token = register_user()
    if not token:
        token = login_user()
    
    if not token:
        log_error("Impossible de continuer les tests sans token d'authentification")
        return
    
    # Test des sessions
    session = create_session(token)
    if not session:
        log_error("Impossible de continuer les tests sans session")
        return
    
    # Récupérer la liste des sessions pour obtenir l'ID correct
    sessions = get_sessions(token)
    if not sessions or len(sessions) == 0:
        log_error("Impossible de récupérer les sessions")
        return
    
    # Utiliser l'ID de la première session (celle que nous venons de créer)
    session_id = sessions[0]["id"]
    log_info(f"Utilisation de la session avec ID: {session_id}")
    
    # Récupérer la session spécifique
    session_detail = get_session(token, session_id)
    if not session_detail:
        log_error("Impossible de récupérer les détails de la session")
    
    # Mettre à jour la session
    updated_session = update_session(token, session_id)
    if not updated_session:
        log_error("Impossible de mettre à jour la session")
    
    # Créer un message
    message = create_message(token, session_id)
    if not message:
        log_error("Impossible de créer un message")
        return
    
    # Récupérer les messages pour obtenir l'ID correct
    messages = get_messages(token, session_id)
    if not messages or len(messages) == 0:
        log_error("Impossible de récupérer les messages")
        return
    
    # Utiliser l'ID du premier message (celui que nous venons de créer)
    message_id = messages[0]["id"]
    log_info(f"Utilisation du message avec ID: {message_id}")
    
    # Tester le streaming
    streaming_result = test_streaming(token, session_id)
    
    # Créer un feedback
    feedback = create_feedback(token, message_id)
    if not feedback:
        log_error("Impossible de créer un feedback")
        return
    
    # Récupérer le feedback spécifique pour obtenir l'ID correct
    message_feedback = get_message_feedback(token, message_id)
    if not message_feedback:
        log_error("Impossible de récupérer le feedback du message")
        return
    
    # Utiliser l'ID du feedback récupéré
    feedback_id = message_feedback["id"]
    log_info(f"Utilisation du feedback avec ID: {feedback_id}")
    
    # Récupérer les feedbacks
    feedbacks = get_feedbacks(token)
    if not feedbacks:
        log_error("Impossible de récupérer les feedbacks")
    
    # Mettre à jour le feedback
    updated_feedback = update_feedback(token, feedback_id)
    if not updated_feedback:
        log_error("Impossible de mettre à jour le feedback")
    
    # Récupérer les feedbacks de la session
    session_feedbacks = get_session_feedbacks(token, session_id)
    if not session_feedbacks:
        log_error("Impossible de récupérer les feedbacks de la session")
    
    # Récupérer les statistiques
    stats = get_feedback_stats(token)
    if not stats:
        log_error("Impossible de récupérer les statistiques")
    
    # Supprimer le feedback
    feedback_deleted = delete_feedback(token, feedback_id)
    if not feedback_deleted:
        log_error("Impossible de supprimer le feedback")
    
    # Supprimer la session
    session_deleted = delete_session(token, session_id)
    if not session_deleted:
        log_error("Impossible de supprimer la session")
    
    log_section("FIN DES TESTS")

if __name__ == "__main__":
    run_tests() 