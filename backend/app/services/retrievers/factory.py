from sqlalchemy.orm import Session

from backend.app.services.retrievers.base import BaseRetriever
from backend.app.services.retrievers.postgres import HybridRetriever


def get_retriever(db: Session) -> BaseRetriever:
    return HybridRetriever(db)
