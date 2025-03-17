from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

from app.api import auth, chat, documents
from app.db.mongodb import connect_to_mongo, close_mongo_connection
from app.db import milvus as milvus_utils
from app import config

# Configurer le logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Créer l'application FastAPI
app = FastAPI(
    title=config.APP_NAME,
    description="Backend FastAPI pour chatbot LLM avec fonctionnalités RAG",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configurer CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # À remplacer par les domaines autorisés en production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Événements de démarrage et d'arrêt
@app.on_event("startup")
async def startup_event():
    logger.info("Application startup...")
    await connect_to_mongo()
    await milvus_utils.connect_to_milvus()

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutdown...")
    await close_mongo_connection()
    await milvus_utils.close_milvus_connection()

# Middleware pour le logging des requêtes
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Request: {request.method} {request.url}")
    response = await call_next(request)
    return response

# Route de vérification de l'état
@app.get("/health")
async def health_check():
    return {"status": "ok"}

# Monter les routers API
app.include_router(auth.router, prefix=config.API_PREFIX, tags=["Authentication"])
app.include_router(chat.router, prefix=config.API_PREFIX, tags=["Chat"])
app.include_router(documents.router, prefix=config.API_PREFIX, tags=["Documents"])

# Gestionnaire d'exceptions
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=config.DEBUG)
