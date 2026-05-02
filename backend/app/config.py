import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DEFAULT_POSTGRES_URL = "postgresql+psycopg2://study_planner:change-me-local-only@127.0.0.1:5433/study_planner"

DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_POSTGRES_URL)
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
STORAGE_DIR = Path(os.getenv("STORAGE_DIR", "./storage/uploads"))
