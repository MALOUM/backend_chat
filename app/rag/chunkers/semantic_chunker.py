from typing import List, Dict, Any
import re
from langchain.text_splitter import RecursiveCharacterTextSplitter
from app.rag.chunkers.text_chunker import TextChunk

class SemanticChunker:
    """Chunker basé sur le sens sémantique (paragraphes, sections, etc.)."""
    
    async def chunk_text(
        self,
        text: str,
        chunk_size: int = 512,
        chunk_overlap: int = 50
    ) -> List[TextChunk]:
        """
        Découper le texte en chunks basés sur le sens sémantique.
        Cela utilise des heuristiques pour identifier les limites naturelles du texte.
        """
        # Pour commencer, essayer de diviser par sections/paragraphes
        paragraphs = re.split(r'\n\s*\n', text)
        
        # Si les paragraphes sont trop longs, les diviser davantage
        chunks = []
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
        )
        
        current_position = 0
        for para in paragraphs:
            if len(para) > chunk_size:
                # Le paragraphe est trop long, utiliser le text splitter
                para_docs = text_splitter.create_documents([para])
                
                for doc in para_docs:
                    end_position = current_position + len(doc.page_content)
                    chunks.append(TextChunk(
                        text=doc.page_content,
                        metadata={
                            "start": current_position,
                            "end": end_position,
                            "is_paragraph": False
                        }
                    ))
                    current_position = end_position - chunk_overlap
            else:
                # Utiliser le paragraphe entier comme chunk
                end_position = current_position + len(para)
                chunks.append(TextChunk(
                    text=para,
                    metadata={
                        "start": current_position,
                        "end": end_position,
                        "is_paragraph": True
                    }
                ))
                current_position = end_position
        
        # Ajouter l'index de chunk
        for i, chunk in enumerate(chunks):
            chunk.metadata["chunk_index"] = i
        
        return chunks