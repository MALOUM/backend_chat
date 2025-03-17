# Documentation API

Ce document décrit toutes les API disponibles dans l'application backend.

## Table des matières

- [Authentification](#authentification)
  - [Inscription](#inscription)
  - [Connexion](#connexion)
  - [Récupérer l'utilisateur actuel](#récupérer-lutilisateur-actuel)
- [Documents](#documents)
  - [Créer un document](#créer-un-document)
  - [Télécharger un document](#télécharger-un-document)
  - [Récupérer tous les documents](#récupérer-tous-les-documents)
  - [Récupérer un document](#récupérer-un-document)
  - [Mettre à jour un document](#mettre-à-jour-un-document)
  - [Supprimer un document](#supprimer-un-document)
  - [Récupérer les chunks d'un document](#récupérer-les-chunks-dun-document)
  - [Traiter un document](#traiter-un-document)
  - [Rechercher des documents](#rechercher-des-documents)
  - [Recherche avancée](#recherche-avancée)
- [Chat](#chat)
  - [Créer une conversation](#créer-une-conversation)
  - [Récupérer les conversations](#récupérer-les-conversations)
  - [Récupérer une conversation](#récupérer-une-conversation)
  - [Supprimer une conversation](#supprimer-une-conversation)
  - [Envoyer un message](#envoyer-un-message)
  - [Récupérer les messages](#récupérer-les-messages)

## Authentification

### Inscription

Crée un nouvel utilisateur.

**URL** : `/api/auth/register`

**Méthode** : `POST`

**Authentification requise** : Non

**Corps de la requête** :
```json
{
  "email": "user@example.com",
  "password": "password123",
  "full_name": "John Doe",
  "username": "johndoe"
}
```

**Réponse réussie** :
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### Connexion

Authentifie un utilisateur et renvoie un token JWT.

**URL** : `/api/auth/login`

**Méthode** : `POST`

**Authentification requise** : Non

**Corps de la requête** :
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

**Réponse réussie** :
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### Récupérer l'utilisateur actuel

Récupère les informations de l'utilisateur actuellement authentifié.

**URL** : `/api/auth/me`

**Méthode** : `GET`

**Authentification requise** : Oui

**Réponse réussie** :
```json
{
  "id": "67d774b5f74f561493342052",
  "email": "user@example.com",
  "username": "johndoe",
  "full_name": "John Doe",
  "is_active": true
}
```

## Documents

### Créer un document

Crée un nouveau document.

**URL** : `/api/documents`

**Méthode** : `POST`

**Authentification requise** : Oui

**Corps de la requête** :
```json
{
  "title": "Document sur l'immigration",
  "content": "Ce document contient des informations importantes sur les procédures d'immigration au Canada.",
  "type": "text",
  "metadata": {
    "source": "Manuel d'immigration",
    "author": "Service d'immigration",
    "created_date": "2023-01-01",
    "tags": ["immigration", "canada", "visa"]
  }
}
```

**Réponse réussie** :
```json
{
  "id": "356a2235-81c1-4eb0-80ed-efbfbbe1efca",
  "user_id": "67d774b5f74f561493342052",
  "title": "Document sur l'immigration",
  "type": "text",
  "url": null,
  "status": "pending",
  "metadata": {
    "source": "Manuel d'immigration",
    "author": "Service d'immigration",
    "created_date": "2023-01-01",
    "tags": ["immigration", "canada", "visa"],
    "properties": {
      "original_id": "356a2235-81c1-4eb0-80ed-efbfbbe1efca"
    }
  },
  "created_at": "2025-03-17T01:03:05.213097",
  "updated_at": "2025-03-17T01:03:05.213097"
}
```

### Télécharger un document

Télécharge un fichier et crée un document.

**URL** : `/api/documents/upload`

**Méthode** : `POST`

**Authentification requise** : Oui

**Corps de la requête** : `multipart/form-data`
- `title` (string, obligatoire) : Titre du document
- `file` (file, obligatoire) : Fichier à télécharger
- `metadata` (string, optionnel) : Métadonnées au format JSON
- `chunking_method` (string, optionnel) : Méthode de découpage (RECURSIVE, FIXED_SIZE, SEMANTIC, SENTENCE, PARAGRAPH)
- `chunk_size` (integer, optionnel) : Taille des chunks
- `chunk_overlap` (integer, optionnel) : Chevauchement des chunks
- `embedding_model` (string, optionnel) : Modèle d'embedding à utiliser
- `process_now` (boolean, optionnel) : Traiter immédiatement le document

**Réponse réussie** :
```json
{
  "id": "8084c1d244454144b9d226d26cd2256c",
  "user_id": "67d75d77363abcfeacfa4086",
  "title": "Test Document Final",
  "type": "pdf",
  "url": null,
  "status": "pending",
  "metadata": {
    "source": null,
    "author": null,
    "created_date": null,
    "tags": [],
    "properties": {
      "original_filename": "imm5690f.pdf",
      "file_size": 1234567
    }
  },
  "created_at": "2025-03-17T00:45:12.123456",
  "updated_at": "2025-03-17T00:45:12.123456"
}
```

### Récupérer tous les documents

Récupère tous les documents de l'utilisateur.

**URL** : `/api/documents`

**Méthode** : `GET`

**Authentification requise** : Oui

**Paramètres de requête** :
- `skip` (integer, optionnel) : Nombre de documents à sauter (pagination)
- `limit` (integer, optionnel) : Nombre maximum de documents à renvoyer (pagination)

**Réponse réussie** :
```json
[
  {
    "id": "67d774d1f74f561493342054",
    "user_id": "67d774b5f74f561493342052",
    "title": "Document sur les visas",
    "type": "text",
    "url": null,
    "status": "completed",
    "metadata": {
      "source": null,
      "author": null,
      "created_date": null,
      "tags": [],
      "properties": {
        "original_id": "c3488f9d-0996-4146-a705-73249bd57256",
        "chunks_count": 1
      }
    },
    "created_at": "2025-03-17T01:03:13.350000",
    "updated_at": "2025-03-17T01:05:31.712000"
  }
]
```

### Récupérer un document

Récupère un document spécifique.

**URL** : `/api/documents/{document_id}`

**Méthode** : `GET`

**Authentification requise** : Oui

**Réponse réussie** :
```json
{
  "id": "67d774d1f74f561493342054",
  "user_id": "67d774b5f74f561493342052",
  "title": "Document sur les visas",
  "type": "text",
  "url": null,
  "status": "completed",
  "metadata": {
    "source": null,
    "author": null,
    "created_date": null,
    "tags": [],
    "properties": {
      "original_id": "c3488f9d-0996-4146-a705-73249bd57256",
      "chunks_count": 1
    }
  },
  "created_at": "2025-03-17T01:03:13.350000",
  "updated_at": "2025-03-17T01:05:31.712000"
}
```

### Mettre à jour un document

Met à jour un document existant.

**URL** : `/api/documents/{document_id}`

**Méthode** : `PUT`

**Authentification requise** : Oui

**Corps de la requête** :
```json
{
  "title": "Document Mis à jour",
  "content": "Contenu mis à jour",
  "metadata": {
    "tags": ["visa", "immigration", "mis à jour"]
  }
}
```

**Réponse réussie** :
```json
{
  "id": "67d7733ef74f561493342051",
  "user_id": "67d76a61437cffebd29b9795",
  "title": "Document Mis à jour",
  "type": "text",
  "url": null,
  "status": "pending",
  "metadata": {
    "source": null,
    "author": null,
    "created_date": null,
    "tags": ["visa", "immigration", "mis à jour"],
    "properties": {
      "original_id": "dcc7e0e0-a311-42be-9a87-3eb688bc6525"
    }
  },
  "created_at": "2025-03-17T00:56:30.515000",
  "updated_at": "2025-03-17T00:59:26.931000"
}
```

### Supprimer un document

Supprime un document.

**URL** : `/api/documents/{document_id}`

**Méthode** : `DELETE`

**Authentification requise** : Oui

**Réponse réussie** : `204 No Content`

### Récupérer les chunks d'un document

Récupère les chunks d'un document.

**URL** : `/api/documents/{document_id}/chunks`

**Méthode** : `GET`

**Authentification requise** : Oui

**Paramètres de requête** :
- `chunking_strategy` (string, optionnel) : Stratégie de découpage
- `chunk_size` (integer, optionnel) : Taille des chunks
- `chunk_overlap` (integer, optionnel) : Chevauchement des chunks

**Réponse réussie** :
```json
[
  {
    "id": "chunk_1",
    "document_id": "67d774d1f74f561493342054",
    "chunk_index": 0,
    "content": "Voici le deuxième document qui parle des visas et des permis de travail. Les procédures peuvent varier selon le pays d'origine.",
    "metadata": {
      "document_id": "67d774d1f74f561493342054",
      "chunk_id": "0"
    }
  }
]
```

### Traiter un document

Lance le traitement d'un document.

**URL** : `/api/documents/{document_id}/process`

**Méthode** : `POST`

**Authentification requise** : Oui

**Corps de la requête** :
```json
{
  "chunking_config": {
    "chunk_size": 1000,
    "chunk_overlap": 200,
    "chunking_method": "recursive"
  },
  "embedding_config": {
    "model_name": "all-MiniLM-L6-v2",
    "dimension": 384,
    "batch_size": 32
  }
}
```

**Réponse réussie** :
```json
{
  "document_id": "67d774d1f74f561493342054",
  "status": "processing",
  "message": "Traitement du document lancé avec succès",
  "chunks_count": null,
  "error": null
}
```

### Rechercher des documents

Recherche des documents par similarité sémantique.

**URL** : `/api/documents/search-documents`

**Méthode** : `GET`

**Authentification requise** : Oui

**Paramètres de requête** :
- `query` (string, obligatoire) : Requête de recherche
- `top_k` (integer, optionnel) : Nombre maximum de résultats à renvoyer
- `embedding_model` (string, optionnel) : Modèle d'embedding à utiliser
- `user_id` (string, optionnel) : ID de l'utilisateur (pour les administrateurs)
- `document_type` (string, optionnel) : Type de document à rechercher

**Réponse réussie** :
```json
{
  "results": [
    {
      "document_id": "dcc7e0e0-a311-42be-9a87-3eb688bc6525",
      "chunk_id": "310329d222cf428abd7ad2a073dc6114",
      "content": "Voici le deuxième document qui parle des visas et des permis de travail. Les procédures peuvent varier selon le pays d'origine.",
      "score": 1.060551404953003,
      "document_title": null,
      "document_type": null
    }
  ],
  "total": 1,
  "query": "visa"
}
```

### Recherche avancée

Recherche avancée de documents avec plus d'options.

**URL** : `/api/documents/search-advanced`

**Méthode** : `POST`

**Authentification requise** : Oui

**Corps de la requête** :
```json
{
  "query": "visa",
  "document_id": null,
  "max_results": 2
}
```

**Réponse réussie** :
```json
{
  "results": [
    {
      "document_id": "dcc7e0e0-a311-42be-9a87-3eb688bc6525",
      "chunk_id": "310329d222cf428abd7ad2a073dc6114",
      "content": "Voici le deuxième document qui parle des visas et des permis de travail. Les procédures peuvent varier selon le pays d'origine.",
      "score": 1.060551404953003,
      "document_title": null,
      "document_type": null
    }
  ],
  "total": 1,
  "query": "visa"
}
```

## Chat

### Créer une conversation

Crée une nouvelle conversation.

**URL** : `/api/chat/conversations`

**Méthode** : `POST`

**Authentification requise** : Oui

**Corps de la requête** :
```json
{
  "title": "Conversation sur l'immigration",
  "context": "Discussion sur les procédures d'immigration au Canada",
  "model": "gpt-3.5-turbo"
}
```

**Réponse réussie** :
```json
{
  "id": "67d774e5f74f561493342055",
  "user_id": "67d774b5f74f561493342052",
  "title": "Conversation sur l'immigration",
  "context": "Discussion sur les procédures d'immigration au Canada",
  "model": "gpt-3.5-turbo",
  "created_at": "2025-03-17T01:10:00.000000",
  "updated_at": "2025-03-17T01:10:00.000000"
}
```

### Récupérer les conversations

Récupère toutes les conversations de l'utilisateur.

**URL** : `/api/chat/conversations`

**Méthode** : `GET`

**Authentification requise** : Oui

**Paramètres de requête** :
- `skip` (integer, optionnel) : Nombre de conversations à sauter (pagination)
- `limit` (integer, optionnel) : Nombre maximum de conversations à renvoyer (pagination)

**Réponse réussie** :
```json
[
  {
    "id": "67d774e5f74f561493342055",
    "user_id": "67d774b5f74f561493342052",
    "title": "Conversation sur l'immigration",
    "context": "Discussion sur les procédures d'immigration au Canada",
    "model": "gpt-3.5-turbo",
    "created_at": "2025-03-17T01:10:00.000000",
    "updated_at": "2025-03-17T01:10:00.000000"
  }
]
```

### Récupérer une conversation

Récupère une conversation spécifique.

**URL** : `/api/chat/conversations/{conversation_id}`

**Méthode** : `GET`

**Authentification requise** : Oui

**Réponse réussie** :
```json
{
  "id": "67d774e5f74f561493342055",
  "user_id": "67d774b5f74f561493342052",
  "title": "Conversation sur l'immigration",
  "context": "Discussion sur les procédures d'immigration au Canada",
  "model": "gpt-3.5-turbo",
  "created_at": "2025-03-17T01:10:00.000000",
  "updated_at": "2025-03-17T01:10:00.000000"
}
```

### Supprimer une conversation

Supprime une conversation.

**URL** : `/api/chat/conversations/{conversation_id}`

**Méthode** : `DELETE`

**Authentification requise** : Oui

**Réponse réussie** : `204 No Content`

### Envoyer un message

Envoie un message dans une conversation.

**URL** : `/api/chat/conversations/{conversation_id}/messages`

**Méthode** : `POST`

**Authentification requise** : Oui

**Corps de la requête** :
```json
{
  "content": "Quelles sont les étapes pour obtenir un visa de travail au Canada?",
  "use_rag": true,
  "rag_config": {
    "query": "visa travail Canada",
    "top_k": 3,
    "filter": {
      "document_type": "text"
    }
  }
}
```

**Réponse réussie** :
```json
{
  "id": "67d774f0f74f561493342056",
  "conversation_id": "67d774e5f74f561493342055",
  "role": "assistant",
  "content": "Pour obtenir un visa de travail au Canada, vous devez suivre plusieurs étapes...",
  "created_at": "2025-03-17T01:11:00.000000",
  "metadata": {
    "sources": [
      {
        "document_id": "67d774d1f74f561493342054",
        "chunk_id": "0",
        "content": "Voici le deuxième document qui parle des visas et des permis de travail...",
        "score": 0.92
      }
    ],
    "tokens": {
      "prompt": 150,
      "completion": 200,
      "total": 350
    },
    "model": "gpt-3.5-turbo"
  }
}
```

### Récupérer les messages

Récupère les messages d'une conversation.

**URL** : `/api/chat/conversations/{conversation_id}/messages`

**Méthode** : `GET`

**Authentification requise** : Oui

**Paramètres de requête** :
- `skip` (integer, optionnel) : Nombre de messages à sauter (pagination)
- `limit` (integer, optionnel) : Nombre maximum de messages à renvoyer (pagination)

**Réponse réussie** :
```json
[
  {
    "id": "67d774f0f74f561493342056",
    "conversation_id": "67d774e5f74f561493342055",
    "role": "assistant",
    "content": "Pour obtenir un visa de travail au Canada, vous devez suivre plusieurs étapes...",
    "created_at": "2025-03-17T01:11:00.000000",
    "metadata": {
      "sources": [
        {
          "document_id": "67d774d1f74f561493342054",
          "chunk_id": "0",
          "content": "Voici le deuxième document qui parle des visas et des permis de travail...",
          "score": 0.92
        }
      ],
      "tokens": {
        "prompt": 150,
        "completion": 200,
        "total": 350
      },
      "model": "gpt-3.5-turbo"
    }
  },
  {
    "id": "67d774e8f74f561493342057",
    "conversation_id": "67d774e5f74f561493342055",
    "role": "user",
    "content": "Quelles sont les étapes pour obtenir un visa de travail au Canada?",
    "created_at": "2025-03-17T01:10:30.000000",
    "metadata": {}
  }
]
``` 