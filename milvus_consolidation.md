# Consolidation des implémentations Milvus

## Problème identifié

Actuellement, le projet contient deux implémentations différentes pour interagir avec Milvus :

1. `app/db/milvus.py` - Une implémentation de bas niveau qui interagit directement avec l'API pymilvus
2. `app/ingestion_service/vector_store/milvus_store.py` - Une implémentation de plus haut niveau qui utilise l'abstraction `VectorStore`

Cette redondance crée plusieurs problèmes :
- Duplication de code
- Risque d'incohérence
- Confusion pour les développeurs
- Problèmes de compatibilité à gérer à plusieurs endroits

## Solution proposée

### 1. Transformer `app/db/milvus.py` en module utilitaire

Ce module ne devrait contenir que des fonctions de bas niveau pour interagir avec Milvus :

```python
"""
Module utilitaire pour les opérations de base avec Milvus.
Ce module fournit des fonctions de bas niveau pour interagir avec Milvus.
Pour les opérations de plus haut niveau, utilisez app.ingestion_service.vector_store.milvus_store.MilvusStore.
"""

from pymilvus import connections, Collection, utility
from pymilvus import CollectionSchema, FieldSchema, DataType
import logging
from typing import Optional, Dict, Any, List

from app import config

logger = logging.getLogger(__name__)

# Variables globales pour la connexion Milvus
_connection_established = False
_collection_cache = {}

def get_connection_params():
    """Récupère les paramètres de connexion à Milvus depuis la configuration."""
    return {
        "host": config.MILVUS_HOST,
        "port": config.MILVUS_PORT,
        "user": config.MILVUS_USER,
        "password": config.MILVUS_PASSWORD,
        "secure": False,
        "timeout": 10
    }

async def connect_to_milvus(alias: str = "default"):
    """
    Établit une connexion à Milvus.
    
    Args:
        alias: Alias de la connexion
        
    Returns:
        True si la connexion est établie avec succès, False sinon
    """
    global _connection_established
    
    if _connection_established:
        return True
    
    try:
        params = get_connection_params()
        connections.connect(alias=alias, **params)
        
        # Vérifier la disponibilité de Milvus
        if hasattr(utility, 'is_connection_healthy'):
            available = utility.is_connection_healthy(alias)
        else:
            available = connections.has_connection(alias)
            
        if available:
            logger.info(f"Connexion à Milvus établie (alias: {alias})")
            _connection_established = True
            return True
        else:
            logger.warning(f"Connexion à Milvus établie mais non disponible (alias: {alias})")
            return False
            
    except Exception as e:
        logger.error(f"Erreur lors de la connexion à Milvus: {e}")
        return False

async def close_milvus_connection(alias: str = "default"):
    """
    Ferme la connexion à Milvus.
    
    Args:
        alias: Alias de la connexion à fermer
    """
    global _connection_established
    
    try:
        # Libérer les collections en cache
        for collection_name, collection in _collection_cache.items():
            try:
                collection.release()
                logger.debug(f"Collection '{collection_name}' libérée")
            except Exception as e:
                logger.warning(f"Erreur lors de la libération de la collection '{collection_name}': {e}")
        
        # Vider le cache
        _collection_cache.clear()
        
        # Fermer la connexion
        connections.disconnect(alias)
        _connection_established = False
        logger.info(f"Connexion à Milvus fermée (alias: {alias})")
    except Exception as e:
        logger.error(f"Erreur lors de la fermeture de la connexion à Milvus: {e}")

async def get_collection(collection_name: str, create_if_missing: bool = False, dimension: int = None):
    """
    Récupère une collection Milvus, la crée si nécessaire.
    
    Args:
        collection_name: Nom de la collection
        create_if_missing: Si True, crée la collection si elle n'existe pas
        dimension: Dimension des vecteurs (obligatoire si create_if_missing=True)
        
    Returns:
        Collection Milvus ou None en cas d'erreur
    """
    # Vérifier si la collection est en cache
    if collection_name in _collection_cache:
        return _collection_cache[collection_name]
    
    # S'assurer que la connexion est établie
    if not _connection_established:
        connected = await connect_to_milvus()
        if not connected:
            return None
    
    try:
        # Vérifier si la collection existe
        if utility.has_collection(collection_name):
            collection = Collection(name=collection_name)
            collection.load()
            _collection_cache[collection_name] = collection
            logger.info(f"Collection '{collection_name}' chargée")
            return collection
        elif create_if_missing and dimension:
            # Créer la collection
            collection = await create_collection(collection_name, dimension)
            _collection_cache[collection_name] = collection
            return collection
        else:
            logger.warning(f"Collection '{collection_name}' non trouvée")
            return None
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de la collection '{collection_name}': {e}")
        return None

async def create_collection(collection_name: str, dimension: int):
    """
    Crée une nouvelle collection Milvus.
    
    Args:
        collection_name: Nom de la collection
        dimension: Dimension des vecteurs d'embedding
        
    Returns:
        Collection créée ou None en cas d'erreur
    """
    try:
        # Définir les champs de la collection
        id_field = FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=100, is_primary=True)
        document_id_field = FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=100)
        chunk_id_field = FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=100)
        content_field = FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=8192)
        embedding_field = FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dimension)
        
        # Créer le schéma et la collection
        schema = CollectionSchema(
            fields=[id_field, document_id_field, chunk_id_field, content_field, embedding_field],
            description="Collection de vecteurs d'embeddings pour RAG"
        )
        
        collection = Collection(name=collection_name, schema=schema)
        
        # Créer un index pour rechercher par similarité
        index_params = {
            "metric_type": "COSINE",
            "index_type": "HNSW",
            "params": {"M": 8, "efConstruction": 64}
        }
        collection.create_index(field_name="embedding", index_params=index_params)
        collection.load()
        
        logger.info(f"Collection '{collection_name}' créée et indexée")
        return collection
    except Exception as e:
        logger.error(f"Erreur lors de la création de la collection '{collection_name}': {e}")
        return None
```

### 2. Modifier `app/ingestion_service/vector_store/milvus_store.py` pour utiliser le module utilitaire

```python
"""
Module implémentant un store de vecteurs avec Milvus.
"""

import os
import uuid
import logging
import asyncio
from typing import List, Dict, Any, Optional, Tuple, Union
import time

from langchain.schema import Document
from app.ingestion_service.embedding.base_embedding import EmbeddingModel
from app.ingestion_service.vector_store.base_store import VectorStore
from app.db import milvus as milvus_utils
from app import config

logger = logging.getLogger(__name__)


class MilvusStore(VectorStore):
    """
    Store de vecteurs utilisant Milvus.
    
    Milvus est une base de données vectorielle open-source, 
    performante et scalable, spécialement conçue pour les 
    recherches de similarité.
    
    Cette implémentation utilise les fonctions utilitaires du module app.db.milvus
    pour interagir avec Milvus de manière cohérente dans toute l'application.
    """
    
    def __init__(
        self,
        embedding_model: EmbeddingModel,
        collection_name: str,
        host: Optional[str] = None,
        port: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None
    ):
        """
        Initialise le store Milvus.
        
        Args:
            embedding_model: Modèle d'embedding à utiliser
            collection_name: Nom de la collection Milvus
            host: Hôte Milvus (ignoré, utilise la configuration globale)
            port: Port Milvus (ignoré, utilise la configuration globale)
            user: Utilisateur Milvus (ignoré, utilise la configuration globale)
            password: Mot de passe Milvus (ignoré, utilise la configuration globale)
        """
        super().__init__(embedding_model, collection_name)
        
        # Ignorer les paramètres de connexion spécifiques et utiliser la configuration globale
        self._dimension = self.embedding_model.dimension
        self._collection = None
        
        logger.info(f"Store Milvus configuré - collection: {collection_name}, dimension: {self._dimension}")
    
    async def _get_collection(self):
        """
        Obtient la collection Milvus, la crée si nécessaire.
        
        Returns:
            Collection Milvus
        """
        if self._collection is None:
            # Établir la connexion à Milvus si nécessaire
            connected = await milvus_utils.connect_to_milvus()
            if not connected:
                raise RuntimeError("Impossible de se connecter à Milvus")
            
            # Récupérer ou créer la collection
            self._collection = await milvus_utils.get_collection(
                collection_name=self.collection_name,
                create_if_missing=True,
                dimension=self._dimension
            )
            
            if self._collection is None:
                raise RuntimeError(f"Impossible de récupérer ou créer la collection '{self.collection_name}'")
        
        return self._collection
    
    @property
    def is_empty(self) -> bool:
        """
        Vérifie si la collection est vide.
        
        Returns:
            True si la collection est vide, False sinon
        """
        try:
            stats = asyncio.run(self.get_collection_stats())
            return stats["count"] == 0
        except Exception:
            # En cas d'erreur, considérer que la collection n'existe pas
            return True
    
    async def add_documents(self, documents: List[Document]) -> Dict[str, Any]:
        """
        Ajoute des documents à la collection Milvus.
        
        Args:
            documents: Liste de documents à ajouter
            
        Returns:
            Dictionnaire contenant les IDs générés
        """
        if not documents:
            logger.warning("Tentative d'ajout d'une liste vide de documents")
            return {"ids": []}
        
        try:
            # Extraire les textes et métadonnées
            texts = [doc.page_content for doc in documents]
            metadata_list = [doc.metadata for doc in documents]
            
            # Utiliser add_texts pour l'insertion
            result = await self.add_texts(texts, metadata_list)
            
            logger.info(f"Documents ajoutés à la collection Milvus: {len(documents)}")
            return result
            
        except Exception as e:
            logger.error(f"Erreur lors de l'ajout de documents: {str(e)}")
            raise
    
    async def add_texts(
        self,
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Ajoute des textes à la collection Milvus.
        
        Args:
            texts: Liste de textes à ajouter
            metadatas: Liste de métadonnées associées aux textes
            
        Returns:
            Dictionnaire contenant les IDs générés
        """
        if not texts:
            logger.warning("Tentative d'ajout d'une liste vide de textes")
            return {"ids": []}
        
        # S'assurer que la collection est disponible
        collection = await self._get_collection()
        
        try:
            # Générer les embeddings
            embeddings = await self.embedding_model.embed_documents(texts)
            
            # Préparer les données pour l'insertion
            ids = [str(uuid.uuid4()) for _ in range(len(texts))]
            document_ids = [meta.get("document_id", "") for meta in metadatas or [{}] * len(texts)]
            chunk_ids = [meta.get("chunk_id", str(i)) for i, meta in enumerate(metadatas or [{}] * len(texts))]
            
            # Préparer les données pour Milvus
            insert_data = {
                "id": ids,
                "document_id": document_ids,
                "chunk_id": chunk_ids,
                "content": texts,
                "embedding": embeddings
            }
            
            # Insérer dans Milvus
            collection.insert(insert_data)
            
            logger.info(f"Textes ajoutés à la collection Milvus: {len(texts)}")
            return {"ids": ids}
            
        except Exception as e:
            logger.error(f"Erreur lors de l'ajout de textes: {str(e)}")
            raise
    
    async def similarity_search(
        self,
        query: str,
        k: int = 4,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """
        Recherche les documents similaires à une requête.
        
        Args:
            query: Requête textuelle
            k: Nombre de résultats à renvoyer
            filter: Filtre supplémentaire pour la recherche
            
        Returns:
            Liste de documents similaires
        """
        # Générer l'embedding de la requête
        embedding = await self.embedding_model.embed_query(query)
        
        # Utiliser la recherche par vecteur
        return await self.similarity_search_by_vector(embedding, k, filter)
    
    async def similarity_search_by_vector(
        self,
        embedding: List[float],
        k: int = 4,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[Document]:
        """
        Recherche les documents similaires à un vecteur d'embedding.
        
        Args:
            embedding: Vecteur d'embedding
            k: Nombre de résultats à renvoyer
            filter: Filtre supplémentaire pour la recherche
            
        Returns:
            Liste de documents similaires
        """
        # S'assurer que la collection est disponible
        collection = await self._get_collection()
        
        try:
            # Préparer les paramètres de recherche
            search_params = {"metric_type": "COSINE", "params": {"ef": 64}}
            
            # Préparer l'expression de filtre si nécessaire
            expr = None
            if filter:
                expr_parts = []
                for key, value in filter.items():
                    if isinstance(value, str):
                        expr_parts.append(f"{key} == '{value}'")
                    else:
                        expr_parts.append(f"{key} == {value}")
                expr = " && ".join(expr_parts)
            
            # Exécuter la recherche
            results = collection.search(
                data=[embedding],
                anns_field="embedding",
                param=search_params,
                limit=k,
                expr=expr,
                output_fields=["document_id", "chunk_id", "content"]
            )
            
            # Convertir les résultats en objets Document
            documents = []
            if results and len(results) > 0:
                for i, hit in enumerate(results[0]):
                    # Extraire les données
                    content = hit.entity.get("content")
                    document_id = hit.entity.get("document_id")
                    chunk_id = hit.entity.get("chunk_id")
                    
                    # Créer les métadonnées
                    metadata = {
                        "document_id": document_id,
                        "chunk_id": chunk_id,
                        "score": hit.distance
                    }
                    
                    # Créer le document
                    doc = Document(page_content=content, metadata=metadata)
                    documents.append(doc)
            
            logger.info(f"Recherche terminée - trouvé {len(documents)} résultats")
            return documents
            
        except Exception as e:
            logger.error(f"Erreur lors de la recherche: {str(e)}")
            raise
    
    async def delete(self, ids: Optional[List[str]] = None, filter: Optional[Dict[str, Any]] = None) -> None:
        """
        Supprime des documents de la collection Milvus.
        
        Args:
            ids: Liste d'identifiants de documents à supprimer
            filter: Filtre pour sélectionner les documents à supprimer
        """
        # S'assurer que la collection est disponible
        collection = await self._get_collection()
        
        try:
            if ids:
                # Suppression par IDs
                collection.delete(f"id in {ids}")
                logger.info(f"Documents supprimés par IDs: {len(ids)}")
            
            elif filter:
                # Préparer l'expression de filtre
                expr_parts = []
                for key, value in filter.items():
                    if isinstance(value, str):
                        expr_parts.append(f"{key} == '{value}'")
                    else:
                        expr_parts.append(f"{key} == {value}")
                expr = " && ".join(expr_parts)
                
                # Suppression par filtre
                collection.delete(expr)
                logger.info(f"Documents supprimés par filtre: {filter}")
            
            else:
                logger.warning("Aucun ID ou filtre fourni, aucune suppression effectuée")
            
        except Exception as e:
            logger.error(f"Erreur lors de la suppression: {str(e)}")
            raise
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """
        Renvoie des statistiques sur la collection Milvus.
        
        Returns:
            Dictionnaire contenant les statistiques
        """
        # S'assurer que la collection est disponible
        collection = await self._get_collection()
        
        try:
            # Obtenir les statistiques
            stats = collection.num_entities
            
            # Formater les statistiques
            result = {
                "collection_name": self.collection_name,
                "count": stats,
                "dimension": self._dimension,
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des statistiques: {str(e)}")
            # En cas d'erreur, renvoyer des statistiques minimales
            return {
                "collection_name": self.collection_name,
                "count": 0,
                "dimension": self._dimension,
                "error": str(e)
            }
```

### 3. Mettre à jour les importations dans le reste du code

Rechercher toutes les références à `app.db.milvus` et les remplacer par des références à `app.ingestion_service.vector_store.milvus_store.MilvusStore` lorsqu'il s'agit d'opérations de haut niveau.

### 4. Mettre à jour `app/main.py`

Modifier les fonctions de démarrage et d'arrêt pour utiliser les nouvelles fonctions utilitaires :

```python
@app.on_event("startup")
async def startup_event():
    logger.info("Application startup...")
    await connect_to_mongo()
    await milvus_utils.connect_to_milvus()

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutdown...")
    await close_mongo_connection()
    await milvus_utils.close_milvus_connection()
```

## Avantages de cette approche

1. **Séparation des responsabilités** : Le module utilitaire gère les opérations de bas niveau, tandis que la classe `MilvusStore` fournit une interface de plus haut niveau.

2. **Réduction de la duplication** : Les fonctionnalités communes sont centralisées dans le module utilitaire.

3. **Cohérence** : Une seule façon d'interagir avec Milvus dans toute l'application.

4. **Facilité de maintenance** : Les problèmes de compatibilité peuvent être gérés à un seul endroit.

## Étapes de mise en œuvre

1. Sauvegarder les fichiers existants
2. Mettre à jour `app/db/milvus.py` avec le nouveau code utilitaire
3. Mettre à jour `app/ingestion_service/vector_store/milvus_store.py` pour utiliser le module utilitaire
4. Mettre à jour `app/main.py` pour utiliser les nouvelles fonctions
5. Tester l'application pour s'assurer que tout fonctionne correctement 