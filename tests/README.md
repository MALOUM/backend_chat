# Tests pour le Backend Chat

Ce dossier contient des outils de test pour vérifier différentes fonctionnalités du backend de chat.

## Test d'annulation du streaming

Le script `test_abort_streaming.py` permet de tester facilement la fonctionnalité d'annulation (abort) 
des générations de réponses en streaming via une interface Streamlit conviviale.

### Prérequis

- Python 3.8+
- Les dépendances listées dans `requirements.txt`

### Installation

```bash
cd tests
pip install -r requirements.txt
```

### Exécution

1. Assurez-vous que le backend est en cours d'exécution sur `http://localhost:8000`
2. Lancez l'application Streamlit :

```bash
cd tests
streamlit run test_abort_streaming.py
```

3. Ouvrez votre navigateur à l'adresse indiquée (généralement `http://localhost:8501`)

### Fonctionnalités du test

L'application propose une interface complète pour tester la fonctionnalité d'annulation :

1. **Authentification** : Connexion à l'API pour obtenir un token
2. **Gestion des sessions** : Création ou sélection d'une session existante 
3. **Test de streaming** : 
   - Saisie d'un message (idéalement long pour avoir le temps d'annuler)
   - Démarrage du streaming qui affiche la réponse en temps réel
   - Bouton d'annulation pour interrompre la génération

### Comment fonctionne l'annulation

L'annulation du streaming utilise les fonctionnalités suivantes implémentées dans le backend :

1. Suivi des tâches actives via un dictionnaire `active_tasks`
2. Signaux d'annulation `asyncio.Event` pour interrompre les générations
3. Endpoint `/api/chat/cancel/{message_id}` pour déclencher l'annulation
4. Message spécial `[CANCELLED]` envoyé dans le stream SSE

Cette interface de test permet de vérifier que tout ce mécanisme fonctionne correctement
en visualisant directement le résultat de l'annulation. 