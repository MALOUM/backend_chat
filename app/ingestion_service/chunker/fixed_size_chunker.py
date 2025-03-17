"""
Module implémentant un chunker à taille fixe pour les documents.
"""

import logging
from typing import List, Dict, Any, Optional

from langchain.schema import Document
from langchain.text_splitter import CharacterTextSplitter

from app.ingestion_service.chunker.base_chunker import DocumentChunker

logger = logging.getLogger(__name__)


class FixedSizeChunker(DocumentChunker):
    """
    Chunker qui divise les documents en chunks de taille fixe.
    
    Ce chunker utilise une stratégie simple basée sur le nombre de caractères,
    sans tenir compte de la structure sémantique du texte. Il est utile pour
    les cas où on souhaite une taille constante de chunks.
    """
    
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        """
        Initialise le chunker à taille fixe.
        
        Args:
            chunk_size: Taille des chunks en nombre de caractères
            chunk_overlap: Chevauchement entre les chunks consécutifs
        """
        super().__init__(chunk_size, chunk_overlap)
        self._validate_parameters()
    
    async def split(self, documents: List[Document]) -> List[Document]:
        """
        Divise une liste de documents en chunks de taille fixe.
        
        Args:
            documents: Liste de documents à découper
            
        Returns:
            Liste de chunks (documents plus petits)
            
        Raises:
            ValueError: Si la liste de documents est vide
        """
        if not documents:
            logger.warning("Liste de documents vide fournie au chunker à taille fixe")
            return []
        
        logger.info(f"Découpage de {len(documents)} documents en chunks "
                   f"de taille fixe {self.chunk_size} avec chevauchement {self.chunk_overlap}")
        
        try:
            # Créer le text splitter à taille fixe
            text_splitter = CharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                separator="\n"  # Utiliser les sauts de ligne comme séparateur préféré
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
                    # Pour les chunks à taille fixe, ajouter des métadonnées sur la position
                    # relative dans le document
                    if len(chunks) > 1:
                        chunk.metadata["position"] = "début" if j == 0 else (
                            "fin" if j == len(chunks) - 1 else "milieu"
                        )
                
                all_chunks.extend(chunks)
            
            logger.info(f"Découpage à taille fixe terminé: {len(all_chunks)} chunks créés au total")
            return all_chunks
            
        except Exception as e:
            logger.error(f"Erreur lors du découpage à taille fixe: {str(e)}")
            raise ValueError(f"Échec du découpage à taille fixe: {str(e)}")
    
    def _calculate_optimal_chunk_size(self, text: str) -> int:
        """
        Calcule la taille optimale des chunks en fonction du texte.
        
        Cette méthode pourrait être utilisée pour ajuster automatiquement
        la taille des chunks en fonction de la longueur totale du texte.
        
        Args:
            text: Texte à analyser
            
        Returns:
            Taille optimale des chunks
        """
        # Pour l'instant, utiliser la taille fixe configurée
        # Cette méthode pourrait être améliorée avec une analyse plus sophistiquée
        return self.chunk_size 