"""
Loader pour les documents PDF.
"""

import os
import logging
from typing import List, Dict, Any
import asyncio

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document

from app.ingestion_service.loader.base_loader import DocumentLoader

logger = logging.getLogger(__name__)

class PdfLoader(DocumentLoader):
    """
    Loader pour les documents PDF.
    Utilise PyPDFLoader de LangChain pour l'extraction du texte.
    """
    
    def __init__(self, source: str):
        """
        Initialise le loader avec le chemin du fichier PDF.
        
        Args:
            source: Chemin vers le fichier PDF
        """
        super().__init__(source)
        
        if not os.path.exists(source) and not source.startswith(('http://', 'https://')):
            raise ValueError(f"Le fichier PDF n'existe pas: {source}")
    
    async def load(self) -> List[Document]:
        """
        Charge le document PDF et renvoie une liste de documents LangChain.
        Chaque page du PDF devient un document séparé.
        
        Returns:
            Liste de documents LangChain (un par page)
        """
        try:
            # PyPDFLoader n'est pas asynchrone, donc on utilise run_in_executor
            loop = asyncio.get_event_loop()
            
            # Créer le loader et charger le document de manière non bloquante
            def _load_pdf():
                loader = PyPDFLoader(self.source)
                return loader.load()
            
            # Exécuter le chargement dans un thread séparé pour ne pas bloquer
            documents = await loop.run_in_executor(None, _load_pdf)
            
            logger.info(f"Document PDF chargé avec succès: {self.source} - {len(documents)} pages")
            
            # Ajouter des métadonnées supplémentaires
            for i, doc in enumerate(documents):
                doc.metadata["source"] = self.source
                doc.metadata["page"] = i + 1
                doc.metadata["total_pages"] = len(documents)
            
            return documents
        
        except Exception as e:
            logger.error(f"Erreur lors du chargement du PDF: {self.source} - {str(e)}")
            # On essaie une méthode alternative si la première échoue
            try:
                logger.info(f"Tentative avec une méthode alternative pour: {self.source}")
                from PyPDF2 import PdfReader
                
                def _load_pdf_alternative():
                    reader = PdfReader(self.source)
                    result = []
                    for i, page in enumerate(reader.pages):
                        text = page.extract_text()
                        if text:
                            doc = Document(
                                page_content=text,
                                metadata={
                                    "source": self.source,
                                    "page": i + 1,
                                    "total_pages": len(reader.pages)
                                }
                            )
                            result.append(doc)
                    return result
                
                documents = await loop.run_in_executor(None, _load_pdf_alternative)
                logger.info(f"Document PDF chargé avec la méthode alternative: {self.source} - {len(documents)} pages")
                return documents
            
            except Exception as e2:
                logger.error(f"Échec de la méthode alternative pour PDF: {self.source} - {str(e2)}")
                raise ValueError(f"Impossible de charger le document PDF: {str(e)} / {str(e2)}")
    
    async def get_metadata(self) -> Dict[str, Any]:
        """
        Extrait les métadonnées du document PDF.
        
        Returns:
            Dictionnaire de métadonnées
        """
        try:
            # Extraction des métadonnées de base
            metadata = {
                "source": self.source,
                "type": "pdf",
                "filename": os.path.basename(self.source)
            }
            
            # Tentative d'extraction de métadonnées avancées
            loop = asyncio.get_event_loop()
            
            def _extract_metadata():
                try:
                    from PyPDF2 import PdfReader
                    reader = PdfReader(self.source)
                    
                    # Métadonnées avancées si disponibles
                    pdf_info = reader.metadata
                    if pdf_info:
                        for key, value in pdf_info.items():
                            if key.startswith('/'):
                                clean_key = key[1:].lower()
                                metadata[clean_key] = value
                    
                    # Nombre de pages
                    metadata["page_count"] = len(reader.pages)
                    
                except Exception as e:
                    logger.warning(f"Impossible d'extraire les métadonnées avancées du PDF: {str(e)}")
                
                return metadata
            
            return await loop.run_in_executor(None, _extract_metadata)
        
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction des métadonnées du PDF: {str(e)}")
            # Retourner au minimum les métadonnées de base
            return {
                "source": self.source,
                "type": "pdf",
                "filename": os.path.basename(self.source),
                "error": str(e)
            } 