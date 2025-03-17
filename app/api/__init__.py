"""
Module regroupant toutes les routes de l'API.
"""

from fastapi import APIRouter
from app.api import auth, chat, documents

api_router = APIRouter()

# Inclure les différents routers
api_router.include_router(auth.router)
api_router.include_router(chat.router)
api_router.include_router(documents.router)
