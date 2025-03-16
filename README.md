# Backend Chat API

API backend pour une application de chat avec fonctionnalités RAG (Retrieval Augmented Generation).

## Caractéristiques

- 🔐 **Authentification** : Système complet d'enregistrement et de connexion avec JWT
- 💬 **Sessions de chat** : Gestion des conversations avec historique
- 🔍 **RAG** : Utilisation de documents externes pour améliorer les réponses
- 📊 **Feedback utilisateur** : Récupération et analyse des retours utilisateurs
- 📄 **Gestion de documents** : Upload et indexation vectorielle

## Documentation

- [Documentation d'authentification](docs/authentication.md) - Guide détaillé sur l'API d'authentification
- Documentation des sessions de chat (à venir)
- Documentation du RAG (à venir)
- Documentation du feedback (à venir)

## Installation

### Prérequis

- Docker et Docker Compose
- Python 3.8+

### Configuration

1. Cloner le dépôt
   ```bash
   git clone [URL_DU_REPO]
   cd backend_chat
   ```

2. Configurer les variables d'environnement
   ```bash
   cp .env.example .env
   # Éditer le fichier .env avec vos propres paramètres
   ```

3. Lancer l'application avec Docker Compose
   ```bash
   docker-compose up -d
   ```

## Utilisation

L'API sera disponible à l'adresse `http://localhost:8000/`.

- Documentation interactive: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Développement

Pour le développement local sans Docker :

1. Créer un environnement virtuel
   ```bash
   python -m venv venv
   source venv/bin/activate  # Sur Windows: venv\Scripts\activate
   ```

2. Installer les dépendances
   ```bash
   pip install -r requirements.txt
   ```

3. Lancer le serveur de développement
   ```bash
   uvicorn app.main:app --reload
   ```

## Licence

[Licence à spécifier] 