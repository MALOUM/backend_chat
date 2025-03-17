"""
Module implémentant un chunker sémantique pour les documents.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
import numpy as np

from langchain.schema import Document
from langchain.text_splitter import TextSplitter, RecursiveCharacterTextSplitter

from app.ingestion_service.chunker.base_chunker import DocumentChunker

logger = logging.getLogger(__name__)


class SemanticChunker(DocumentChunker):
    """
    Chunker qui divise les documents en fonction du sens du contenu.
    
    Ce chunker utilise une approche sémantique pour créer des chunks
    qui préservent au mieux la cohérence sémantique. Il peut utiliser
    des embedding pour déterminer les frontières sémantiques.
    """
    
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200, 
                embedding_model = None):
        """
        Initialise le chunker sémantique.
        
        Args:
            chunk_size: Taille cible des chunks en nombre de caractères
            chunk_overlap: Chevauchement entre les chunks consécutifs
            embedding_model: Modèle d'embedding optionnel pour l'analyse sémantique
        """
        super().__init__(chunk_size, chunk_overlap)
        self._validate_parameters()
        self.embedding_model = embedding_model
        
        # Pour l'instant, utiliser le chunker récursif comme base
        self.base_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap
        )
    
    async def split(self, documents: List[Document]) -> List[Document]:
        """
        Divise une liste de documents en chunks en fonction du sens.
        
        Args:
            documents: Liste de documents à découper
            
        Returns:
            Liste de chunks (documents plus petits)
            
        Raises:
            ValueError: Si la liste de documents est vide
        """
        if not documents:
            logger.warning("Liste de documents vide fournie au chunker sémantique")
            return []
        
        logger.info(f"Découpage sémantique de {len(documents)} documents")
        
        try:
            # Si nous n'avons pas de modèle d'embedding, utiliser
            # la méthode récursive avec des heuristiques
            if self.embedding_model is None:
                return await self._split_without_embeddings(documents)
            else:
                return await self._split_with_embeddings(documents)
                
        except Exception as e:
            logger.error(f"Erreur lors du découpage sémantique: {str(e)}")
            raise ValueError(f"Échec du découpage sémantique: {str(e)}")
    
    async def _split_without_embeddings(self, documents: List[Document]) -> List[Document]:
        """
        Divise les documents sans utiliser d'embeddings, en se basant sur
        des heuristiques comme les titres, les paragraphes, etc.
        
        Args:
            documents: Liste de documents à découper
            
        Returns:
            Liste de chunks
        """
        all_chunks = []
        
        for i, doc in enumerate(documents):
            # Extraire le texte et les métadonnées
            text = doc.page_content
            metadata = doc.metadata.copy() if hasattr(doc, "metadata") else {}
            
            # Ajouter des métadonnées spécifiques au document
            metadata["document_index"] = i
            
            # Première étape: découper par sections potentielles
            # (titres, entêtes, lignes vides multiples)
            sections = self._split_by_sections(text)
            
            # Deuxième étape: traiter chaque section pour respecter
            # la taille maximale des chunks
            section_chunks = []
            for section in sections:
                # Si la section est petite, la garder telle quelle
                if len(section) <= self.chunk_size:
                    section_chunks.append(section)
                else:
                    # Sinon, utiliser le chunker récursif
                    sub_chunks = self.base_splitter.split_text(section)
                    section_chunks.extend(sub_chunks)
            
            # Créer les documents à partir des chunks
            chunks = []
            for j, chunk_text in enumerate(section_chunks):
                chunk_metadata = metadata.copy()
                chunk_metadata.update({
                    "chunk_index": j,
                    "total_chunks": len(section_chunks)
                })
                chunks.append(Document(page_content=chunk_text, metadata=chunk_metadata))
            
            all_chunks.extend(chunks)
        
        logger.info(f"Découpage sémantique (sans embeddings) terminé: "
                  f"{len(all_chunks)} chunks créés au total")
        return all_chunks
    
    async def _split_with_embeddings(self, documents: List[Document]) -> List[Document]:
        """
        Divise les documents en utilisant des embeddings pour détecter
        les frontières sémantiques.
        
        Args:
            documents: Liste de documents à découper
            
        Returns:
            Liste de chunks
        """
        logger.info("Utilisation d'embeddings pour le découpage sémantique")
        all_chunks = []
        
        try:
            for i, doc in enumerate(documents):
                # Extraire le texte et les métadonnées
                text = doc.page_content
                metadata = doc.metadata.copy() if hasattr(doc, "metadata") else {}
                
                # Ajouter des métadonnées spécifiques au document
                metadata["document_index"] = i
                
                # Première étape: découper grossièrement en paragraphes
                paragraphs = text.split("\n\n")
                
                # Deuxième étape: calculer l'embedding pour chaque paragraphe
                paragraph_embeddings = []
                for p in paragraphs:
                    if p.strip():  # Ignorer les paragraphes vides
                        embedding = await self._get_embedding(p)
                        if embedding is not None:
                            paragraph_embeddings.append((p, embedding))
                
                # Troisième étape: regrouper les paragraphes par similarité
                # pour former des chunks sémantiquement cohérents
                chunks_text = self._cluster_paragraphs(
                    [p[0] for p in paragraph_embeddings],
                    [p[1] for p in paragraph_embeddings]
                )
                
                # Créer les documents à partir des chunks
                chunks = []
                for j, chunk_text in enumerate(chunks_text):
                    if len(chunk_text) > self.chunk_size:
                        # Si le chunk est trop grand, le redécouper
                        sub_chunks = self.base_splitter.split_text(chunk_text)
                        for k, sub_chunk in enumerate(sub_chunks):
                            sub_metadata = metadata.copy()
                            sub_metadata.update({
                                "chunk_index": f"{j}.{k}",
                                "total_chunks": len(chunks_text),
                                "is_sub_chunk": True
                            })
                            chunks.append(Document(page_content=sub_chunk, metadata=sub_metadata))
                    else:
                        chunk_metadata = metadata.copy()
                        chunk_metadata.update({
                            "chunk_index": j,
                            "total_chunks": len(chunks_text)
                        })
                        chunks.append(Document(page_content=chunk_text, metadata=chunk_metadata))
                
                all_chunks.extend(chunks)
            
            logger.info(f"Découpage sémantique (avec embeddings) terminé: "
                      f"{len(all_chunks)} chunks créés au total")
            return all_chunks
            
        except Exception as e:
            logger.error(f"Erreur lors du découpage sémantique avec embeddings: {str(e)}")
            logger.info("Recours au découpage sans embeddings")
            return await self._split_without_embeddings(documents)
    
    def _split_by_sections(self, text: str) -> List[str]:
        """
        Divise le texte en sections basées sur des marqueurs de section.
        
        Args:
            text: Texte à diviser
            
        Returns:
            Liste des sections
        """
        # Marqueurs de section potentiels
        section_markers = [
            # Titres Markdown
            r"^#+ .*$",
            # Titres numérotés
            r"^\d+\.\s+.*$",
            # Lignes vides multiples
            r"\n\n\n+"
        ]
        
        # Pour l'instant, utilisation simple des paragraphes
        sections = []
        current_section = ""
        
        for paragraph in text.split("\n\n"):
            if len(current_section) + len(paragraph) + 2 <= self.chunk_size:
                if current_section:
                    current_section += "\n\n"
                current_section += paragraph
            else:
                if current_section:
                    sections.append(current_section)
                current_section = paragraph
        
        if current_section:
            sections.append(current_section)
        
        return sections
    
    async def _get_embedding(self, text: str) -> List[float]:
        """
        Calcule l'embedding d'un texte.
        
        Args:
            text: Texte dont on veut calculer l'embedding
            
        Returns:
            Vecteur d'embedding ou None en cas d'échec
        """
        if self.embedding_model is None:
            return None
        
        try:
            embedding = await self.embedding_model.embed_query(text)
            return embedding
        except Exception as e:
            logger.warning(f"Erreur lors du calcul de l'embedding: {str(e)}")
            return None
    
    def _cluster_paragraphs(self, paragraphs: List[str], embeddings: List[List[float]]) -> List[str]:
        """
        Regroupe les paragraphes en chunks sémantiquement cohérents.
        
        Cette méthode utilise les embeddings pour regrouper les paragraphes
        qui sont sémantiquement similaires.
        
        Args:
            paragraphs: Liste des paragraphes
            embeddings: Liste des embeddings correspondants
            
        Returns:
            Liste des chunks regroupés
        """
        # Méthode simple: regrouper les paragraphes jusqu'à atteindre la taille maximale
        chunks = []
        current_chunk = ""
        
        for i, paragraph in enumerate(paragraphs):
            # Si le chunk actuel est vide ou si l'ajout du paragraphe ne dépasse pas la taille maximale
            if not current_chunk or len(current_chunk) + len(paragraph) + 2 <= self.chunk_size:
                if current_chunk:
                    current_chunk += "\n\n"
                current_chunk += paragraph
            else:
                chunks.append(current_chunk)
                current_chunk = paragraph
        
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks 