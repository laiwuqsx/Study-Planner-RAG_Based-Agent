from sqlalchemy import Float, cast, desc, func, literal
from sqlalchemy.orm import Session

from backend.app.database import DATABASE_URL
from backend.app.models import ChildChunk
from backend.app.services.retrievers.base import BaseRetriever


class PostgresKeywordRetriever(BaseRetriever):
    def __init__(self, db: Session):
        self.db = db
        self._is_postgres = DATABASE_URL.startswith("postgresql")

    def index_document(self, *, document_id: int) -> None:
        return None

    def delete_document(self, *, user_id: int, document_id: int) -> None:
        return None

    def search(self, *, query: str, user_id: int, course_id: int, top_k: int) -> list[dict]:
        if self._is_postgres:
            return self._postgres_search(query=query, user_id=user_id, course_id=course_id, top_k=top_k)
        return self._fallback_search(query=query, user_id=user_id, course_id=course_id, top_k=top_k)

    def _postgres_search(self, *, query: str, user_id: int, course_id: int, top_k: int) -> list[dict]:
        vector = func.to_tsvector("english", ChildChunk.text)
        ts_query = func.websearch_to_tsquery("english", query)
        rank = func.ts_rank(vector, ts_query)

        rows = (
            self.db.query(
                ChildChunk.chunk_id,
                ChildChunk.root_chunk_id,
                ChildChunk.parent_chunk_id,
                ChildChunk.document_id,
                ChildChunk.filename,
                ChildChunk.material_type,
                ChildChunk.page_number,
                ChildChunk.section_title,
                ChildChunk.text,
                rank.label("score"),
            )
            .filter(
                ChildChunk.user_id == user_id,
                ChildChunk.course_id == course_id,
                vector.op("@@")(ts_query),
            )
            .order_by(desc(rank), ChildChunk.chunk_index.asc())
            .limit(top_k)
            .all()
        )
        return [self._row_to_result(row) for row in rows]

    def _fallback_search(self, *, query: str, user_id: int, course_id: int, top_k: int) -> list[dict]:
        pattern = f"%{query.strip()}%"
        score = cast(literal(1.0), Float)
        rows = (
            self.db.query(
                ChildChunk.chunk_id,
                ChildChunk.root_chunk_id,
                ChildChunk.parent_chunk_id,
                ChildChunk.document_id,
                ChildChunk.filename,
                ChildChunk.material_type,
                ChildChunk.page_number,
                ChildChunk.section_title,
                ChildChunk.text,
                score.label("score"),
            )
            .filter(
                ChildChunk.user_id == user_id,
                ChildChunk.course_id == course_id,
                ChildChunk.text.ilike(pattern),
            )
            .order_by(ChildChunk.chunk_index.asc())
            .limit(top_k)
            .all()
        )
        return [self._row_to_result(row) for row in rows]

    @staticmethod
    def _row_to_result(row) -> dict:
        return {
            "chunk_id": row.chunk_id,
            "root_chunk_id": row.root_chunk_id,
            "parent_chunk_id": row.parent_chunk_id,
            "document_id": row.document_id,
            "filename": row.filename,
            "material_type": row.material_type,
            "page_number": row.page_number,
            "section_title": row.section_title,
            "text": row.text,
            "score": float(row.score or 0.0),
        }
