from sqlalchemy.orm import Session

from backend.app.services.retrievers.base import BaseRetriever
from backend.app.services.retrievers.postgres import PostgresKeywordRetriever


def get_retriever(db: Session) -> BaseRetriever:
    return PostgresKeywordRetriever(db)
