"""
Module définissant l'interface de base pour les modèles d'embedding.
"""

import abc
import logging
from typing import List, Dict, Any, Optional, Union

logger = logging.getLogger(__name__)


class EmbeddingModel(abc.ABC):
    """
    Classe abstraite définissant l'interface pour les modèles d'embedding.
    Les modèles d'embedding sont responsables de transformer du texte en
    vecteurs numériques qui capturent la sémantique du contenu.
    """
    
    def __init__(self, model_name: Optional[str] = None):
        """
        Initialise le modèle d'embedding.
        
        Args:
            model_name: Nom spécifique du modèle à utiliser (optionnel)
        """
        self.model_name = model_name
        logger.info(f"Initialisation du modèle d'embedding {self.__class__.__name__}, "
                   f"modèle: {model_name or 'par défaut'}")
    
    @abc.abstractmethod
    async def embed_query(self, text: str) -> List[float]:
        """
        Génère un embedding pour une requête (texte unique).
        
        Args:
            text: Texte à transformer en embedding
            
        Returns:
            Vecteur d'embedding
        """
        pass
    
    @abc.abstractmethod
    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Génère des embeddings pour une liste de documents.
        
        Args:
            texts: Liste de textes à transformer en embeddings
            
        Returns:
            Liste de vecteurs d'embedding
        """
        pass
    
    @property
    @abc.abstractmethod
    def dimension(self) -> int:
        """
        Renvoie la dimension des vecteurs d'embedding produits par ce modèle.
        
        Returns:
            Dimension des vecteurs d'embedding
        """
        pass
    
    @abc.abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """
        Renvoie les métadonnées du modèle d'embedding.
        
        Returns:
            Dictionnaire contenant les métadonnées du modèle
        """
        pass
    
    def _validate_text(self, text: Union[str, List[str]]) -> None:
        """
        Valide le texte à transformer en embedding.
        
        Args:
            text: Texte ou liste de textes à valider
            
        Raises:
            ValueError: Si le texte est invalide
        """
        if isinstance(text, str):
            if not text.strip():
                raise ValueError("Le texte à transformer en embedding ne peut pas être vide")
        elif isinstance(text, list):
            if not text:
                raise ValueError("La liste de textes à transformer en embedding ne peut pas être vide")
            for t in text:
                if not isinstance(t, str) or not t.strip():
                    raise ValueError("Tous les éléments de la liste doivent être des chaînes non vides")
        else:
            raise ValueError(f"Type invalide pour le texte: {type(text)}, doit être str ou List[str]") 