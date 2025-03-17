"""
Module pour charger et extraire le texte des images.
"""

import os
import logging
import io
from typing import Dict, List, Optional
import requests
from urllib.parse import urlparse
from datetime import datetime
from PIL import Image
import pytesseract

from langchain.schema import Document
from app.ingestion_service.loader.base_loader import DocumentLoader

logger = logging.getLogger(__name__)


class ImageLoader(DocumentLoader):
    """
    Chargeur pour les images avec extraction de texte via OCR.
    """
    
    def __init__(self, source: str):
        """
        Initialise le chargeur avec la source de l'image.
        
        Args:
            source: Chemin local vers l'image ou URL
        """
        super().__init__(source)
        self.is_url = bool(urlparse(source).scheme)
    
    async def load(self) -> List[Document]:
        """
        Charge l'image et extrait son texte via OCR.
        
        Returns:
            Liste contenant un Document avec le texte extrait de l'image
            
        Raises:
            FileNotFoundError: Si le fichier image n'existe pas
            IOError: Si l'image ne peut pas être chargée ou traitée
        """
        logger.info(f"Chargement et OCR de l'image: {self.source}")
        
        try:
            # Charger l'image
            image = await self._load_image()
            
            # Extraire le texte avec OCR
            text = self._extract_text(image)
            
            # Récupérer les métadonnées
            metadata = await self.get_metadata(image)
            
            # Créer un document Langchain
            doc = Document(page_content=text, metadata=metadata)
            return [doc]
            
        except Exception as e:
            logger.error(f"Erreur lors du traitement de l'image {self.source}: {str(e)}")
            raise
    
    async def _load_image(self) -> Image.Image:
        """
        Charge l'image depuis un fichier local ou une URL.
        
        Returns:
            Objet Image PIL
            
        Raises:
            FileNotFoundError: Si le fichier image n'existe pas
            IOError: Si l'image ne peut pas être chargée
        """
        try:
            if self.is_url:
                response = requests.get(self.source, timeout=15)
                response.raise_for_status()
                return Image.open(io.BytesIO(response.content))
            else:
                if not os.path.exists(self.source):
                    logger.error(f"Fichier image non trouvé: {self.source}")
                    raise FileNotFoundError(f"Le fichier {self.source} n'existe pas")
                
                return Image.open(self.source)
        except Exception as e:
            logger.error(f"Erreur lors du chargement de l'image {self.source}: {str(e)}")
            raise IOError(f"Impossible de charger l'image {self.source}") from e
    
    def _extract_text(self, image: Image.Image) -> str:
        """
        Extrait le texte de l'image via OCR.
        
        Args:
            image: Objet Image PIL
            
        Returns:
            Texte extrait de l'image
            
        Raises:
            Exception: Si l'OCR échoue
        """
        try:
            # Configuration de Tesseract pour de meilleurs résultats
            custom_config = r'--oem 3 --psm 6'
            
            # Conversion en niveaux de gris pour de meilleurs résultats OCR
            gray_image = image.convert('L')
            
            # Extraction du texte
            text = pytesseract.image_to_string(gray_image, config=custom_config)
            
            if not text.strip():
                logger.warning(f"Aucun texte extrait de l'image {self.source}")
                return "Aucun texte détecté dans l'image."
            
            return text
            
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction du texte de l'image {self.source}: {str(e)}")
            raise Exception(f"Échec de l'OCR pour {self.source}: {str(e)}") from e
    
    async def get_metadata(self, image: Optional[Image.Image] = None) -> Dict:
        """
        Extrait les métadonnées de l'image.
        
        Args:
            image: Objet Image PIL (si déjà chargé)
            
        Returns:
            Dictionnaire contenant les métadonnées de l'image
        """
        metadata = {
            "source": self.source,
            "type": "image",
            "is_url": self.is_url,
            "extraction_date": datetime.now().isoformat(),
        }
        
        # Ajouter des métadonnées supplémentaires si l'image est disponible
        if image:
            try:
                metadata.update({
                    "width": image.width,
                    "height": image.height,
                    "format": image.format,
                    "mode": image.mode,
                })
                
                # Extraire les métadonnées EXIF si disponibles
                if hasattr(image, '_getexif') and image._getexif():
                    exif = image._getexif()
                    if exif:
                        # Mappages courants pour les tags EXIF
                        exif_tags = {
                            271: 'make',
                            272: 'model',
                            306: 'date_time',
                            36867: 'date_time_original',
                            33432: 'copyright',
                        }
                        
                        exif_data = {}
                        for tag, value in exif.items():
                            if tag in exif_tags:
                                exif_data[exif_tags[tag]] = str(value)
                        
                        if exif_data:
                            metadata["exif"] = exif_data
            except Exception as e:
                logger.warning(f"Impossible de récupérer toutes les métadonnées pour l'image {self.source}: {str(e)}")
        
        # Ajouter des métadonnées spécifiques aux fichiers locaux
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
                logger.warning(f"Impossible de récupérer les métadonnées du fichier pour {self.source}: {str(e)}")
        
        return metadata 