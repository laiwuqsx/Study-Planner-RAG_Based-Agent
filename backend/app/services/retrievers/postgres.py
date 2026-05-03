from sqlalchemy import Float, cast, desc, func, literal
from sqlalchemy.orm import Session

from backend.app.database import DATABASE_URL
from backend.app.models import ChildChunk
from backend.app.services.embeddings.factory import get_embedder
from backend.app.services.milvus_store import MilvusChunkStore
from backend.app.services.retrievers.base import BaseRetriever


class HybridRetriever(BaseRetriever):
    def __init__(self, db: Session):
        self.db = db
        self._is_postgres = DATABASE_URL.startswith("postgresql")
        self._embedder = get_embedder()
        self._milvus = MilvusChunkStore()

    def index_document(self, *, document_id: int) -> None:
        chunks = (
            self.db.query(ChildChunk)
            .filter(ChildChunk.document_id == document_id)
            .order_by(ChildChunk.chunk_index.asc())
            .all()
        )
        embeddings = self._embedder.embed_texts([chunk.text for chunk in chunks], input_type="document")
        self._milvus.upsert_chunks(chunks, embeddings)

    def delete_document(self, *, user_id: int, document_id: int) -> None:
        self._milvus.delete_document(user_id=user_id, document_id=document_id)

    def search(self, *, query: str, user_id: int, course_id: int, top_k: int, retrieval_mode: str) -> list[dict]:
        mode = retrieval_mode.lower()
        if mode == "keyword":
            return self._keyword_search(query=query, user_id=user_id, course_id=course_id, top_k=top_k)
        if mode == "vector":
            return self._vector_search(query=query, user_id=user_id, course_id=course_id, top_k=top_k)
        if mode == "hybrid":
            return self._hybrid_search(query=query, user_id=user_id, course_id=course_id, top_k=top_k)
        raise ValueError(f"Unsupported retrieval mode: {retrieval_mode}")

    def _keyword_search(self, *, query: str, user_id: int, course_id: int, top_k: int) -> list[dict]:
        if self._is_postgres:
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
        else:
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

    def _vector_search(self, *, query: str, user_id: int, course_id: int, top_k: int) -> list[dict]:
        vector = self._embedder.embed_texts([query], input_type="query")[0]
        return self._milvus.search(vector=vector, user_id=user_id, course_id=course_id, top_k=top_k)

    def _hybrid_search(self, *, query: str, user_id: int, course_id: int, top_k: int) -> list[dict]:
        keyword_results = self._keyword_search(query=query, user_id=user_id, course_id=course_id, top_k=top_k)
        vector_results = self._vector_search(query=query, user_id=user_id, course_id=course_id, top_k=top_k)

        by_chunk_id: dict[str, dict] = {}
        for rank, result in enumerate(keyword_results, start=1):
            entry = by_chunk_id.setdefault(result["chunk_id"], {**result, "score": 0.0})
            entry["score"] += 1.0 / (60 + rank)
        for rank, result in enumerate(vector_results, start=1):
            entry = by_chunk_id.setdefault(result["chunk_id"], {**result, "score": 0.0})
            entry["score"] += 1.0 / (60 + rank)

        return sorted(by_chunk_id.values(), key=lambda item: item["score"], reverse=True)[:top_k]

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
