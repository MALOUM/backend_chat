import os
from dotenv import load_dotenv
from pathlib import Path

# Charger les variables d'environnement depuis .env
load_dotenv()

# Paramètres d'application
APP_NAME = "FastAPI LLM RAG Backend"
API_PREFIX = "/api"
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

# Paramètres de sécurité
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-for-jwt")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# MongoDB
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "llm_rag_app")

# Milvus
MILVUS_HOST = os.getenv("MILVUS_HOST", "milvus-standalone")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")
MILVUS_COLLECTION = os.getenv("MILVUS_COLLECTION", "document_embeddings")
MILVUS_USER = os.getenv("MILVUS_USER", "")
MILVUS_PASSWORD = os.getenv("MILVUS_PASSWORD", "")

# LLM Config
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")  # options: openai, huggingface, lmstudio
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-3.5-turbo")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Hugging Face Config
HF_API_KEY = os.getenv("HF_API_KEY", "")
HF_ENDPOINT = os.getenv("HF_ENDPOINT", "")

# LM Studio Config
LM_STUDIO_BASE_URL = os.getenv("LM_STUDIO_BASE_URL", "http://host.docker.internal:1234/v1")
LM_STUDIO_API_KEY = os.getenv("LM_STUDIO_API_KEY", "lm-studio") 
LM_STUDIO_MODEL = os.getenv("LM_STUDIO_MODEL", "local-model")

# Embedding Config
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "384"))

# RAG Config
DEFAULT_CHUNK_SIZE = int(os.getenv("DEFAULT_CHUNK_SIZE", "512"))
DEFAULT_CHUNK_OVERLAP = int(os.getenv("DEFAULT_CHUNK_OVERLAP", "50"))
TOP_K_RETRIEVAL = int(os.getenv("TOP_K_RETRIEVAL", "5"))

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
TEMP_DIR = BASE_DIR / "temp"
TEMP_DIR.mkdir(exist_ok=True)