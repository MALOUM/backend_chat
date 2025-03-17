"""
Classe de base abstraite pour tous les loaders de documents.
"""

from abc import ABC, abstractmethod
from typing import List

from langchain_core.documents import Document

class DocumentLoader(ABC):
    """
    Interface abstraite pour tous les loaders de documents.
    
    Chaque type de document spécifique (PDF, texte, URL, etc.) doit
    implémenter cette interface pour fournir un comportement cohérent
    quelle que soit la source.
    """
    
    def __init__(self, source: str):
        """
        Initialise le loader avec la source du document.
        
        Args:
            source: Chemin ou URL vers le document
        """
        self.source = source
    
    @abstractmethod
    async def load(self) -> List[Document]:
        """
        Charge le document et renvoie une liste de documents LangChain.
        
        Returns:
            Liste de documents LangChain
        """
        pass
    
    @abstractmethod
    async def get_metadata(self) -> dict:
        """
        Extrait les métadonnées du document.
        
        Returns:
            Dictionnaire de métadonnées
        """
        pass 