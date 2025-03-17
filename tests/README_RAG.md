# Tests du système RAG

Ce dossier contient différents scripts pour tester le système de Retrieval Augmented Generation (RAG) implémenté dans notre application.

## Prérequis

Avant d'exécuter les tests, assurez-vous que :

1. L'application backend est en cours d'exécution sur `http://localhost:8000`
2. MongoDB et Milvus sont correctement configurés et accessibles
3. Les dépendances suivantes sont installées :
   ```bash
   pip install requests sseclient-py langchain langchain-community
   ```

## Scripts de test disponibles

### 1. Test API avec Curl (`test_rag_api.sh`)

Ce script bash teste les fonctionnalités RAG via l'API REST en utilisant curl.

```bash
chmod +x test_rag_api.sh
./test_rag_api.sh
```

Le script teste :
- L'authentification
- La création d'une session
- L'upload d'un document PDF
- L'envoi d'une requête avec RAG activé
- Le streaming de la réponse

### 2. Test des différentes stratégies RAG (`test_rag_strategies.sh`)

Ce script teste successivement les différentes stratégies RAG disponibles.

```bash
chmod +x test_rag_strategies.sh
./test_rag_strategies.sh
```

Il teste les stratégies :
- Basic (recherche par similarité vectorielle simple)
- Ensemble (combinaison de BM25 et recherche vectorielle)
- Reranking (reclassement des résultats)
- Hybrid (combinaison d'ensemble et de reranking)

### 3. Test des endpoints API avec Python (`test_rag_api_endpoints.py`)

Ce script Python teste en détail les endpoints API liés au RAG.

```bash
python test_rag_api_endpoints.py
```

Options disponibles :
```
--url URL_BASE          URL de base de l'API (défaut: http://localhost:8000/api)
--email EMAIL           Email pour l'authentification
--password PASSWORD     Mot de passe pour l'authentification
--pdf CHEMIN_PDF        Chemin vers le fichier PDF à utiliser
```

### 4. Test des modèles d'embedding et stratégies RAG (`test_rag_models.py`)

Ce script teste différentes combinaisons de modèles d'embedding et de stratégies de récupération en utilisant directement les modules LangChain.

```bash
python test_rag_models.py
```

Ce test :
- Charge le document PDF et le divise en chunks
- Teste différents modèles d'embedding (HuggingFace, FastEmbed)
- Teste différentes stratégies de récupération
- Mesure les performances (temps, nombre de documents récupérés)
- Génère un rapport détaillé des résultats

## Interprétation des résultats

### Métriques à observer

- **Nombre de documents récupérés** : Plus élevé n'est pas toujours mieux - l'important est la pertinence
- **Temps de réponse** : Les stratégies plus complexes (hybrid, reranking) peuvent être plus lentes
- **Qualité des réponses** : Vérifiez si les réponses incluent des informations pertinentes du document

### Rapport de test

Après l'exécution de `test_rag_models.py`, un rapport de test est généré avec le format `rag_test_results_YYYYMMDD_HHMMSS.txt`, contenant des statistiques détaillées sur les performances des différentes combinaisons.

## Résolution des problèmes courants

- **Erreur d'authentification** : Vérifiez que l'utilisateur test3@example.com existe et que le mot de passe est correct
- **Erreur d'upload de document** : Vérifiez que le chemin vers le PDF est correct
- **Échec de connexion à l'API** : Assurez-vous que l'application backend est en cours d'exécution
- **Erreur de streaming** : Vérifiez que les services backend sont opérationnels et que l'api SSE fonctionne

## Personnalisation des tests

Vous pouvez modifier les scripts pour tester :
- Différents documents
- D'autres modèles d'embedding
- Des requêtes personnalisées
- Des configurations de chunking différentes 