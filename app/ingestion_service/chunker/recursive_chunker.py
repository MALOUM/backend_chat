"""
Module implémentant un chunker récursif pour les documents.
"""

import logging
from typing import List, Dict, Any, Optional

from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter

from app.ingestion_service.chunker.base_chunker import DocumentChunker

logger = logging.getLogger(__name__)


class RecursiveChunker(DocumentChunker):
    """
    Chunker qui utilise une stratégie de découpage récursif.
    
    Ce chunker divise le texte de manière récursive en utilisant une série de séparateurs
    (paragraphes, phrases, mots) pour créer des chunks qui respectent autant que possible
    les frontières sémantiques naturelles du texte.
    """
    
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        """
        Initialise le chunker récursif.
        
        Args:
            chunk_size: Taille cible des chunks en nombre de caractères
            chunk_overlap: Chevauchement entre les chunks consécutifs
        """
        super().__init__(chunk_size, chunk_overlap)
        self._validate_parameters()
        
        # Définir les séparateurs pour le découpage récursif
        self.separators = [
            "\n\n",   # Paragraphes
            "\n",     # Lignes
            ". ",     # Phrases
            ", ",     # Clauses
            " ",      # Mots
            ""        # Caractères
        ]
    
    async def split(self, documents: List[Document]) -> List[Document]:
        """
        Divise une liste de documents en chunks en utilisant une stratégie récursive.
        
        Args:
            documents: Liste de documents à découper
            
        Returns:
            Liste de chunks (documents plus petits)
            
        Raises:
            ValueError: Si la liste de documents est vide
        """
        if not documents:
            logger.warning("Liste de documents vide fournie au chunker récursif")
            return []
        
        logger.info(f"Découpage récursif de {len(documents)} documents en chunks "
                   f"de taille {self.chunk_size} avec chevauchement {self.chunk_overlap}")
        
        try:
            # Créer le text splitter
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                separators=self.separators
            )
            
            # Collecter tous les chunks
            all_chunks = []
            
            for i, doc in enumerate(documents):
                # Extraire le texte et les métadonnées
                text = doc.page_content
                metadata = doc.metadata.copy() if hasattr(doc, "metadata") else {}
                
                # Ajouter des métadonnées spécifiques au document
                metadata["document_index"] = i
                
                # Découper le document
                chunks = text_splitter.create_documents([text], [metadata])
                
                # Ajouter des métadonnées sur les chunks
                for j, chunk in enumerate(chunks):
                    chunk.metadata["chunk_index"] = j
                    chunk.metadata["total_chunks"] = len(chunks)
                
                all_chunks.extend(chunks)
            
            logger.info(f"Découpage terminé: {len(all_chunks)} chunks créés au total")
            return all_chunks
            
        except Exception as e:
            logger.error(f"Erreur lors du découpage récursif: {str(e)}")
            raise ValueError(f"Échec du découpage récursif: {str(e)}")
    
    def _get_optimal_separators(self, text: str) -> List[str]:
        """
        Détermine les séparateurs optimaux pour le texte donné.
        
        Cette méthode analyse le texte pour déterminer quels séparateurs
        sont les plus pertinents en fonction de leur fréquence dans le texte.
        
        Args:
            text: Texte à analyser
            
        Returns:
            Liste des séparateurs optimaux
        """
        # Pour l'instant, utiliser les séparateurs par défaut
        # Cette méthode pourrait être améliorée avec une analyse plus sophistiquée
        return self.separators 