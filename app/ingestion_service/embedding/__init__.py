"""
Module des embeddings pour les documents.

Ce module fournit des classes pour générer des embeddings vectoriels à partir de textes:
- OpenAIEmbedding: Utilise l'API OpenAI pour générer des embeddings de haute qualité
- HuggingFaceEmbedding: Utilise des modèles de Hugging Face pour des embeddings locaux
- FastEmbedEmbedding: Utilise la bibliothèque FastEmbed pour des embeddings rapides

Les embeddings sont des représentations vectorielles du texte qui capturent
le sens sémantique, permettant des recherches par similarité.
"""

from app.ingestion_service.embedding.factory import EmbeddingFactory
from app.ingestion_service.embedding.base_embedding import EmbeddingModel
from app.ingestion_service.embedding.openai_embedding import OpenAIEmbedding
from app.ingestion_service.embedding.huggingface_embedding import HuggingFaceEmbedding
from app.ingestion_service.embedding.fastembed_embedding import FastEmbedEmbedding

__all__ = [
    'EmbeddingFactory',
    'EmbeddingModel',
    'OpenAIEmbedding',
    'HuggingFaceEmbedding',
    'FastEmbedEmbedding'
] 