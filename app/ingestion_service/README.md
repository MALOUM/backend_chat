# Service d'Ingestion de Documents

Ce service fournit une architecture modulaire pour traiter, vectoriser et rechercher des documents à l'aide de la technologie RAG (Retrieval Augmented Generation).

## Architecture

Le service d'ingestion est structuré en plusieurs modules :

1. **Loaders** : Chargent différents types de documents (PDF, texte, URL, images)
2. **Chunkers** : Découpent les documents en fragments pertinents
3. **Embedding** : Génèrent des embeddings vectoriels pour les chunks
4. **Vector Store** : Stockent et recherchent des vecteurs dans une base de données vectorielle
5. **Document Processor** : Orchestrateur qui coordonne le flux complet

## Utilisation Programmatique

### Exemple simple

```python
from app.ingestion_service import DocumentProcessor

# Créer un processeur avec des paramètres par défaut
processor = DocumentProcessor()

# Traiter un document
result = await processor.process_document("chemin/vers/document.pdf")

# Rechercher des informations
chunks = await processor.retrieve_similar("Quelle est la principale information?", k=3)
```

### Exemple avec configuration personnalisée

```python
from app.ingestion_service import DocumentProcessor

# Créer un processeur avec configuration personnalisée
processor = DocumentProcessor(
    loader_type="pdf",
    chunker_type="recursive",
    embedding_type="openai",
    store_type="milvus",
    collection_name="mes_documents",
    chunker_params={
        "chunk_size": 800,
        "chunk_overlap": 150
    },
    embedding_params={
        "model_name": "text-embedding-3-small"
    }
)

# Traiter un document
result = await processor.process_document("chemin/vers/document.pdf")

# Rechercher avec filtrage par ID de document
chunks = await processor.retrieve_similar(
    "Que dit le document sur les impôts?",
    k=5,
    filter={"document_id": result["document_id"]}
)
```

## API REST

Le service expose également une API REST pour l'ingestion et la recherche de documents :

### Téléchargement de documents

```
POST /ingestion/upload
```

Paramètres :
- `file` : Fichier à télécharger (multipart/form-data)
- `params` : Paramètres d'ingestion au format JSON (optionnel)
- `run_async` : Booléen pour exécuter en arrière-plan (optionnel)

Exemple de corps de requête :
```json
{
  "chunker_type": "recursive",
  "embedding_type": "openai",
  "chunk_size": 1000,
  "chunk_overlap": 200
}
```

### Recherche de documents

```
POST /ingestion/search
```

Exemple de corps de requête :
```json
{
  "query": "Quelles sont les principales informations de ce document?",
  "document_id": "a1b2c3d4-e5f6-g7h8-i9j0-k1l2m3n4o5p6",
  "max_results": 5
}
```

### Vérification du statut d'une tâche asynchrone

```
GET /ingestion/status/{task_id}
```

### Suppression d'un document

```
DELETE /ingestion/documents/{document_id}
```

## Configuration

Le service utilise les variables d'environnement suivantes :

- `OPENAI_API_KEY` : Clé API pour OpenAI (si utilisation d'embeddings OpenAI)
- `MILVUS_HOST` : Hôte Milvus (par défaut : "localhost")
- `MILVUS_PORT` : Port Milvus (par défaut : "19530")
- `MILVUS_USER` : Utilisateur Milvus (optionnel)
- `MILVUS_PASSWORD` : Mot de passe Milvus (optionnel)

## Extension

Le système est conçu pour être extensible :

1. Ajoutez de nouveaux loaders en créant des classes qui héritent de `DocumentLoader`
2. Ajoutez de nouveaux chunkers en créant des classes qui héritent de `TextChunker`
3. Ajoutez de nouveaux modèles d'embedding en créant des classes qui héritent de `EmbeddingModel`
4. Ajoutez de nouveaux stores vectoriels en créant des classes qui héritent de `VectorStore`

Ensuite, enregistrez vos nouvelles classes dans les factories correspondantes. 