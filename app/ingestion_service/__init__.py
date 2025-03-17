"""
Service d'ingestion pour le traitement des documents.

Ce service fournit une architecture modulaire pour:
1. Charger divers types de documents (PDF, texte, URL, images)
2. Découper ces documents en chunks pertinents
3. Générer des embeddings à l'aide de différents modèles
4. Stocker ces embeddings dans une base de données vectorielle
5. Rechercher des documents similaires à partir de requêtes textuelles

Les composants principaux sont:
- loader: Modules pour charger différents types de documents
- chunker: Modules pour diviser les documents en chunks
- embedding: Modules pour générer des embeddings
- vector_store: Modules pour stocker et rechercher des embeddings
- orchestrator: Classe centrale qui coordonne le processus complet
"""

from app.ingestion_service.orchestrator import IngestionOrchestrator, process_document

__all__ = [
    "IngestionOrchestrator",
    "process_document"
] 