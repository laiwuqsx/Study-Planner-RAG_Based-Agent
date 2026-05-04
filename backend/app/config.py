import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DEFAULT_POSTGRES_URL = "postgresql+psycopg2://study_planner:change-me-local-only@127.0.0.1:5433/study_planner"

DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_POSTGRES_URL)
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", "./storage/uploads"))
MILVUS_HOST = os.getenv("MILVUS_HOST", "127.0.0.1")
MILVUS_PORT = os.getenv("MILVUS_PORT", "19531")
MILVUS_URI = os.getenv("MILVUS_URI", f"http://{MILVUS_HOST}:{MILVUS_PORT}")
MILVUS_COLLECTION = os.getenv("MILVUS_COLLECTION", "study_chunks")
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "voyage")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "voyage-4-lite")
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "1024"))
VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY", "")
CHAT_PROVIDER = os.getenv("CHAT_PROVIDER", "auto")
CHAT_MODEL = os.getenv("CHAT_MODEL", "gpt-4.1-mini")
CHAT_API_KEY = os.getenv("CHAT_API_KEY", "")
CHAT_BASE_URL = os.getenv("CHAT_BASE_URL", "https://api.openai.com/v1")
CHAT_MAX_OUTPUT_TOKENS = int(os.getenv("CHAT_MAX_OUTPUT_TOKENS", "500"))
