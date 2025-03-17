"""
Module des loaders de documents.

Ce module fournit des classes pour charger différents types de documents:
- PDF
- Texte
- URL
- Images

Chaque loader est responsable du chargement et de l'extraction du contenu
d'un type de document spécifique, ainsi que de la récupération des métadonnées associées.
"""

from app.ingestion_service.loader.base_loader import DocumentLoader
from app.ingestion_service.loader.pdf_loader import PdfLoader
from app.ingestion_service.loader.text_loader import TextLoader
from app.ingestion_service.loader.url_loader import UrlLoader
from app.ingestion_service.loader.image_loader import ImageLoader
from app.ingestion_service.loader.factory import LoaderFactory

__all__ = [
    'DocumentLoader',
    'PdfLoader',
    'TextLoader',
    'UrlLoader',
    'ImageLoader',
    'LoaderFactory'
] 