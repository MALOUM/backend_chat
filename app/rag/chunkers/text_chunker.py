from typing import List, Dict, Any
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document as LangChainDocument

class TextChunk:
    """Classe représentant un chunk de texte."""
    
    def __init__(self, text: str, metadata: Dict[str, Any] = None):
        self.text = text
        self.metadata = metadata or {}

class FixedSizeChunker:
    """Chunker basé sur une taille fixe."""
    
    async def chunk_text(
        self,
        text: str,
        chunk_size: int = 512,
        chunk_overlap: int = 50
    ) -> List[TextChunk]:
        """
        Découper le texte en chunks de taille fixe.
        """
        # Utiliser le text splitter de LangChain
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            is_separator_regex=False,
        )
        
        # Découper le texte
        langchain_docs = text_splitter.create_documents([text])
        
        # Convertir en TextChunk
        chunks = []
        for i, doc in enumerate(langchain_docs):
            chunks.append(TextChunk(
                text=doc.page_content,
                metadata={
                    "chunk_index": i,
                    "start": doc.metadata.get("start", 0),
                    "end": doc.metadata.get("end", 0)
                }
            ))
        
        return chunks