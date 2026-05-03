from pymilvus import DataType, MilvusClient

from backend.app.config import EMBEDDING_DIMENSION, MILVUS_COLLECTION, MILVUS_URI
from backend.app.models import ChildChunk


class MilvusChunkStore:
    def __init__(self):
        self.client = MilvusClient(uri=MILVUS_URI)
        self._ensure_collection()

    def upsert_chunks(self, chunks: list[ChildChunk], embeddings: list[list[float]]) -> None:
        if not chunks:
            return
        self.delete_document(document_id=chunks[0].document_id, user_id=chunks[0].user_id)
        rows = []
        for chunk, embedding in zip(chunks, embeddings, strict=True):
            rows.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "user_id": chunk.user_id,
                    "course_id": chunk.course_id,
                    "document_id": chunk.document_id,
                    "parent_chunk_id": chunk.parent_chunk_id,
                    "root_chunk_id": chunk.root_chunk_id,
                    "filename": chunk.filename,
                    "material_type": chunk.material_type,
                    "page_number": chunk.page_number or -1,
                    "section_title": chunk.section_title or "",
                    "text": chunk.text,
                    "embedding": embedding,
                }
            )
        self.client.insert(collection_name=MILVUS_COLLECTION, data=rows)

    def delete_document(self, *, document_id: int, user_id: int) -> None:
        if not self.client.has_collection(collection_name=MILVUS_COLLECTION):
            return
        self.client.delete(
            collection_name=MILVUS_COLLECTION,
            filter=f"user_id == {user_id} and document_id == {document_id}",
        )

    def search(self, *, vector: list[float], user_id: int, course_id: int, top_k: int) -> list[dict]:
        self.client.load_collection(collection_name=MILVUS_COLLECTION)
        rows = self.client.search(
            collection_name=MILVUS_COLLECTION,
            anns_field="embedding",
            data=[vector],
            filter=f"user_id == {user_id} and course_id == {course_id}",
            limit=top_k,
            output_fields=[
                "chunk_id",
                "root_chunk_id",
                "parent_chunk_id",
                "document_id",
                "filename",
                "material_type",
                "page_number",
                "section_title",
                "text",
            ],
            search_params={"metric_type": "COSINE"},
        )
        hits = rows[0] if rows else []
        results: list[dict] = []
        for hit in hits:
            entity = hit.get("entity", {})
            results.append(
                {
                    "chunk_id": entity["chunk_id"],
                    "root_chunk_id": entity["root_chunk_id"],
                    "parent_chunk_id": entity["parent_chunk_id"],
                    "document_id": entity["document_id"],
                    "filename": entity["filename"],
                    "material_type": entity["material_type"],
                    "page_number": None if entity["page_number"] == -1 else entity["page_number"],
                    "section_title": entity["section_title"],
                    "text": entity["text"],
                    "score": float(hit.get("distance", 0.0)),
                }
            )
        return results

    def _ensure_collection(self) -> None:
        if self.client.has_collection(collection_name=MILVUS_COLLECTION):
            self.client.load_collection(collection_name=MILVUS_COLLECTION)
            return

        schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=False)
        schema.add_field("chunk_id", DataType.VARCHAR, is_primary=True, max_length=120)
        schema.add_field("user_id", DataType.INT64)
        schema.add_field("course_id", DataType.INT64)
        schema.add_field("document_id", DataType.INT64)
        schema.add_field("parent_chunk_id", DataType.INT64)
        schema.add_field("root_chunk_id", DataType.VARCHAR, max_length=120)
        schema.add_field("filename", DataType.VARCHAR, max_length=255)
        schema.add_field("material_type", DataType.VARCHAR, max_length=40)
        schema.add_field("page_number", DataType.INT64)
        schema.add_field("section_title", DataType.VARCHAR, max_length=255)
        schema.add_field("text", DataType.VARCHAR, max_length=65535)
        schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=EMBEDDING_DIMENSION)

        index_params = MilvusClient.prepare_index_params()
        index_params.add_index(
            field_name="embedding",
            index_type="AUTOINDEX",
            metric_type="COSINE",
        )

        self.client.create_collection(
            collection_name=MILVUS_COLLECTION,
            schema=schema,
            index_params=index_params,
        )
