# Documentation API d'Authentification

Ce document décrit les endpoints d'authentification disponibles dans l'API de chat et comment les utiliser.

## Endpoints disponibles

L'API d'authentification dispose de quatre endpoints principaux :

### 1. Enregistrement d'un utilisateur

- **URL** : `/api/auth/register`
- **Méthode** : `POST`
- **Corps de la requête** (JSON) :
  ```json
  {
    "username": "nom_utilisateur",
    "email": "utilisateur@example.com",
    "password": "MotDePasse123!"
  }
  ```
- **Réponse réussie** (200 OK) :
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer"
  }
  ```
- **Exemple avec curl** :
  ```bash
  curl -X POST "http://localhost:8000/api/auth/register" \
    -H "Content-Type: application/json" \
    -d '{"username":"nouvel_utilisateur","email":"nouveau@example.com","password":"MotDePasse123!"}'
  ```

### 2. Connexion (login)

- **URL** : `/api/auth/login`
- **Méthode** : `POST`
- **Corps de la requête** (JSON) :
  ```json
  {
    "email": "utilisateur@example.com",
    "password": "MotDePasse123!"
  }
  ```
- **Réponse réussie** (200 OK) :
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer"
  }
  ```
- **Exemple avec curl** :
  ```bash
  curl -X POST "http://localhost:8000/api/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"email":"utilisateur@example.com","password":"MotDePasse123!"}'
  ```

### 3. Connexion compatible OAuth2

- **URL** : `/api/auth/token`
- **Méthode** : `POST`
- **Corps de la requête** (form-urlencoded) :
  - `username` : email de l'utilisateur
  - `password` : mot de passe de l'utilisateur
- **Réponse réussie** (200 OK) :
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer"
  }
  ```
- **Exemple avec curl** :
  ```bash
  curl -X POST "http://localhost:8000/api/auth/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d 'username=utilisateur@example.com&password=MotDePasse123!'
  ```

### 4. Déconnexion (logout)

- **URL** : `/api/auth/logout`
- **Méthode** : `POST`
- **En-têtes requis** : `Authorization: Bearer <token>`
- **Corps de la requête** : Non requis
- **Réponse réussie** (200 OK) :
  ```json
  {
    "message": "Déconnexion réussie"
  }
  ```
- **Exemple avec curl** :
  ```bash
  curl -X POST "http://localhost:8000/api/auth/logout" \
    -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  ```

## Utilisation du token d'authentification

Après avoir obtenu un token d'authentification, il doit être inclus dans l'en-tête `Authorization` de chaque requête nécessitant une authentification, avec le préfixe `Bearer`.

**Exemple** :
```bash
curl -X GET "http://localhost:8000/api/chat/sessions" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

## Durée de validité du token

Le token d'authentification a une durée de validité limitée (généralement 30 minutes, configurable via la variable `ACCESS_TOKEN_EXPIRE_MINUTES` dans le fichier de configuration). Après expiration, vous devrez vous reconnecter pour obtenir un nouveau token.

## Gestion de la déconnexion

La déconnexion avec des JWT présente des particularités en raison de la nature sans état (stateless) des tokens JWT. Voici les principales approches implémentées dans notre API :

1. **Déconnexion côté client** : Lors de l'appel à l'endpoint `/api/auth/logout`, le client doit supprimer le token de son stockage local (localStorage, sessionStorage, cookie).

2. **Liste de révocation de tokens** : L'API maintient une liste des tokens invalidés dans une base de données. Lorsqu'un utilisateur se déconnecte, son token est ajouté à cette liste jusqu'à sa date d'expiration, rendant le token inutilisable même s'il n'a pas encore expiré.

3. **Sessions actives** : L'API peut également maintenir une liste des sessions actives par utilisateur, permettant à un utilisateur de voir et gérer ses connexions actives sur différents appareils.

## Erreurs courantes

- **401 Unauthorized** : Token manquant, invalide ou expiré
- **400 Bad Request** : Données d'authentification incorrectes
- **409 Conflict** (uniquement pour l'enregistrement) : Nom d'utilisateur ou email déjà utilisé

## Bonnes pratiques de sécurité

1. Utilisez toujours HTTPS en production
2. Ne stockez jamais les tokens dans le localStorage (préférez le sessionStorage ou les cookies HttpOnly)
3. Implémentez un mécanisme de rafraîchissement de token si nécessaire
4. Invalidez les tokens lorsque l'utilisateur se déconnecte
5. Limitez les tentatives de connexion échouées pour prévenir les attaques par force brute 