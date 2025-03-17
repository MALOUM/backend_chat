"""
Factory pour créer des loaders de documents.
"""

import logging
import os
from typing import Optional, Dict, Type, Any

from app.models.document import DocumentType
from app.ingestion_service.loader.base_loader import DocumentLoader
from app.ingestion_service.loader.pdf_loader import PdfLoader
from app.ingestion_service.loader.text_loader import TextLoader 
from app.ingestion_service.loader.url_loader import UrlLoader
from app.ingestion_service.loader.image_loader import ImageLoader

logger = logging.getLogger(__name__)

class LoaderFactory:
    """
    Factory pour créer des loaders de documents.
    Utilise le pattern Factory pour instancier le bon type de loader en fonction du type de document.
    """
    
    # Mapping statique des types de documents vers les classes de loaders
    _loader_map: Dict[str, Type[DocumentLoader]] = {
        "pdf": PdfLoader,
        "text": TextLoader,
        "url": UrlLoader,
        "image": ImageLoader
    }
    
    def __init__(self):
        """
        Initialise la factory avec le mapping des types de documents vers les classes de loaders.
        """
        # Pour compatibilité avec le code existant
        pass
    
    def create_loader(self, document_type: DocumentType, source: str) -> DocumentLoader:
        """
        Crée un loader approprié pour le type de document.
        
        Args:
            document_type: Type de document
            source: Chemin ou URL vers le document
            
        Returns:
            Une instance de DocumentLoader appropriée
            
        Raises:
            ValueError: Si le type de document n'est pas pris en charge
        """
        # Convertir DocumentType en chaîne pour le mapping
        doc_type_str = document_type.value if hasattr(document_type, 'value') else str(document_type).lower()
        
        if doc_type_str not in self._loader_map:
            raise ValueError(f"Type de document non pris en charge: {document_type}")
        
        loader_class = self._loader_map[doc_type_str]
        logger.info(f"Création d'un loader de type {loader_class.__name__} pour {source}")
        
        return loader_class(source)
    
    def register_loader(self, document_type: DocumentType, loader_class: Type[DocumentLoader]) -> None:
        """
        Enregistre un nouveau type de loader dans la factory.
        
        Args:
            document_type: Type de document
            loader_class: Classe de loader
        """
        doc_type_str = document_type.value if hasattr(document_type, 'value') else str(document_type).lower()
        self._loader_map[doc_type_str] = loader_class
        logger.info(f"Loader {loader_class.__name__} enregistré pour le type {document_type}")
    
    def get_supported_types(self) -> list:
        """
        Renvoie la liste des types de documents pris en charge.
        
        Returns:
            Liste des types de documents pris en charge
        """
        return list(self._loader_map.keys())
    
    @staticmethod
    def detect_loader_type(source: str) -> str:
        """
        Détecte automatiquement le type de loader à utiliser en fonction de la source.
        
        Args:
            source: Chemin ou URL vers le document
            
        Returns:
            Type de loader à utiliser
        """
        # Vérifier si c'est une URL
        if source.startswith(('http://', 'https://')):
            return "url"
        
        # Vérifier l'extension du fichier
        _, ext = os.path.splitext(source)
        ext = ext.lower().lstrip('.')
        
        if ext in ['pdf']:
            return "pdf"
        elif ext in ['jpg', 'jpeg', 'png', 'gif']:
            return "image"
        elif ext in ['txt', 'md', 'html', 'htm', 'csv', 'json']:
            return "text"
        else:
            # Par défaut, utiliser le loader de texte
            logger.warning(f"Type de document non reconnu pour {source}, utilisation du loader de texte par défaut")
            return "text"
    
    @staticmethod
    async def create_loader(loader_type: str, source: str) -> DocumentLoader:
        """
        Crée un loader approprié pour le type spécifié.
        
        Args:
            loader_type: Type de loader à créer
            source: Chemin ou URL vers le document
            
        Returns:
            Une instance de DocumentLoader appropriée
            
        Raises:
            ValueError: Si le type de loader n'est pas pris en charge
        """
        loader_type = loader_type.lower()
        
        if loader_type not in LoaderFactory._loader_map:
            raise ValueError(f"Type de loader non pris en charge: {loader_type}")
        
        loader_class = LoaderFactory._loader_map[loader_type]
        logger.info(f"Création d'un loader de type {loader_class.__name__} pour {source}")
        
        return loader_class(source) 