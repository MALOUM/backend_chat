"""
Module pour charger des documents texte.
"""

import os
import logging
import aiofiles
from typing import Dict, List, Optional
import requests
from urllib.parse import urlparse

from langchain.schema import Document
from app.ingestion_service.loader.base_loader import DocumentLoader

logger = logging.getLogger(__name__)


class TextLoader(DocumentLoader):
    """
    Chargeur pour les documents texte (fichiers .txt, .md, etc.)
    """
    
    def __init__(self, source: str):
        """
        Initialise le chargeur avec la source du document.
        
        Args:
            source: Chemin local vers le fichier texte ou URL
        """
        super().__init__(source)
        self.is_url = bool(urlparse(source).scheme)
    
    async def load(self) -> List[Document]:
        """
        Charge le contenu du document texte.
        
        Returns:
            Liste contenant un seul Document avec le contenu du fichier texte
            
        Raises:
            FileNotFoundError: Si le fichier n'existe pas
            IOError: Si le fichier ne peut pas être lu
        """
        logger.info(f"Chargement du fichier texte: {self.source}")
        
        try:
            content = await self._get_content()
            metadata = await self.get_metadata()
            
            # Créer un document Langchain
            doc = Document(page_content=content, metadata=metadata)
            return [doc]
            
        except Exception as e:
            logger.error(f"Erreur lors du chargement du fichier texte {self.source}: {str(e)}")
            raise
    
    async def _get_content(self) -> str:
        """
        Récupère le contenu du document texte depuis un fichier local ou une URL.
        
        Returns:
            Contenu du document sous forme de chaîne de caractères
        """
        if self.is_url:
            try:
                response = requests.get(self.source, timeout=10)
                response.raise_for_status()
                return response.text
            except requests.RequestException as e:
                logger.error(f"Erreur lors de la récupération de l'URL {self.source}: {str(e)}")
                raise IOError(f"Impossible de récupérer le contenu depuis {self.source}") from e
        else:
            if not os.path.exists(self.source):
                logger.error(f"Fichier non trouvé: {self.source}")
                raise FileNotFoundError(f"Le fichier {self.source} n'existe pas")
            
            try:
                async with aiofiles.open(self.source, 'r', encoding='utf-8') as file:
                    return await file.read()
            except Exception as e:
                logger.error(f"Erreur lors de la lecture du fichier {self.source}: {str(e)}")
                raise IOError(f"Impossible de lire le fichier {self.source}") from e
    
    async def get_metadata(self) -> Dict:
        """
        Extrait les métadonnées du document texte.
        
        Returns:
            Dictionnaire contenant les métadonnées du document
        """
        metadata = {
            "source": self.source,
            "type": "text",
            "is_url": self.is_url,
        }
        
        if not self.is_url:
            try:
                file_stats = os.stat(self.source)
                metadata.update({
                    "filename": os.path.basename(self.source),
                    "file_path": os.path.abspath(self.source),
                    "file_size": file_stats.st_size,
                    "created_at": file_stats.st_ctime,
                    "modified_at": file_stats.st_mtime
                })
            except Exception as e:
                logger.warning(f"Impossible de récupérer toutes les métadonnées pour {self.source}: {str(e)}")
        
        return metadata 