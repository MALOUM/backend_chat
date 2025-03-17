"""
Module pour charger des documents à partir d'URLs.
"""

import logging
from typing import Dict, List, Optional
import requests
from urllib.parse import urlparse
from datetime import datetime
from bs4 import BeautifulSoup

from langchain.schema import Document
from app.ingestion_service.loader.base_loader import DocumentLoader

logger = logging.getLogger(__name__)


class UrlLoader(DocumentLoader):
    """
    Chargeur pour les documents provenant d'URLs (pages web, articles, etc.)
    """
    
    def __init__(self, source: str):
        """
        Initialise le chargeur avec l'URL source.
        
        Args:
            source: URL de la page web à charger
        """
        super().__init__(source)
        parsed_url = urlparse(source)
        if not parsed_url.scheme or not parsed_url.netloc:
            raise ValueError(f"URL invalide: {source}")
        self.parsed_url = parsed_url
    
    async def load(self) -> List[Document]:
        """
        Charge le contenu de l'URL et le transforme en document.
        
        Returns:
            Liste contenant un Document avec le contenu de la page web
            
        Raises:
            IOError: Si l'URL ne peut pas être chargée
        """
        logger.info(f"Chargement de l'URL: {self.source}")
        
        try:
            html_content = await self._fetch_url()
            text_content = self._extract_text(html_content)
            metadata = await self.get_metadata(html_content)
            
            # Créer un document Langchain
            doc = Document(page_content=text_content, metadata=metadata)
            return [doc]
            
        except Exception as e:
            logger.error(f"Erreur lors du chargement de l'URL {self.source}: {str(e)}")
            raise IOError(f"Impossible de charger l'URL {self.source}") from e
    
    async def _fetch_url(self) -> str:
        """
        Récupère le contenu HTML de l'URL.
        
        Returns:
            Contenu HTML de la page web
            
        Raises:
            IOError: Si l'URL ne peut pas être récupérée
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(self.source, headers=headers, timeout=15)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"Erreur lors de la récupération de l'URL {self.source}: {str(e)}")
            raise IOError(f"Impossible de récupérer le contenu depuis {self.source}") from e
    
    def _extract_text(self, html_content: str) -> str:
        """
        Extrait le texte principal du contenu HTML.
        
        Args:
            html_content: Contenu HTML de la page web
            
        Returns:
            Texte extrait de la page web
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Supprimer les balises script et style
            for script in soup(['script', 'style', 'header', 'footer', 'nav']):
                script.decompose()
            
            # Récupérer uniquement le contenu principal si possible
            main_content = soup.find('main') or soup.find('article') or soup.find('div', {'id': 'content'}) or soup.body
            
            if not main_content:
                main_content = soup
            
            # Extraire le texte
            text = main_content.get_text(separator='\n', strip=True)
            
            # Nettoyer les sauts de ligne multiples
            import re
            text = re.sub(r'\n+', '\n', text)
            
            return text
            
        except Exception as e:
            logger.warning(f"Erreur lors de l'extraction du texte. Utilisation de l'HTML brut: {str(e)}")
            return BeautifulSoup(html_content, 'html.parser').get_text(separator='\n', strip=True)
    
    async def get_metadata(self, html_content: str = None) -> Dict:
        """
        Extrait les métadonnées de la page web.
        
        Args:
            html_content: Contenu HTML de la page web (si déjà récupéré)
            
        Returns:
            Dictionnaire contenant les métadonnées du document
        """
        metadata = {
            "source": self.source,
            "type": "url",
            "domain": self.parsed_url.netloc,
            "scheme": self.parsed_url.scheme,
            "path": self.parsed_url.path,
            "retrieval_date": datetime.now().isoformat(),
        }
        
        # Extraire les métadonnées depuis les balises meta si html_content est fourni
        if html_content:
            try:
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Titre de la page
                title_tag = soup.find('title')
                if title_tag:
                    metadata["title"] = title_tag.string
                
                # Description
                description_tag = soup.find('meta', attrs={'name': 'description'})
                if description_tag:
                    metadata["description"] = description_tag.get('content', '')
                
                # Open Graph metadata (pour les réseaux sociaux)
                og_title = soup.find('meta', attrs={'property': 'og:title'})
                if og_title:
                    metadata["og_title"] = og_title.get('content', '')
                
                og_description = soup.find('meta', attrs={'property': 'og:description'})
                if og_description:
                    metadata["og_description"] = og_description.get('content', '')
                
                # Auteur
                author_tag = soup.find('meta', attrs={'name': 'author'})
                if author_tag:
                    metadata["author"] = author_tag.get('content', '')
                
            except Exception as e:
                logger.warning(f"Erreur lors de l'extraction des métadonnées HTML: {str(e)}")
        
        return metadata 