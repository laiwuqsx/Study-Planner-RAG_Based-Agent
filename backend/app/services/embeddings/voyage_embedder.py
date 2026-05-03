from voyageai import Client

from backend.app.config import EMBEDDING_DIMENSION, EMBEDDING_MODEL, VOYAGE_API_KEY
from backend.app.services.embeddings.base import BaseEmbedder


class VoyageEmbedder(BaseEmbedder):
    def __init__(self):
        if not VOYAGE_API_KEY:
            raise ValueError("VOYAGE_API_KEY is required when EMBEDDING_PROVIDER=voyage")
        self.client = Client(api_key=VOYAGE_API_KEY)

    def embed_texts(self, texts: list[str], *, input_type: str) -> list[list[float]]:
        if not texts:
            return []
        response = self.client.embed(
            texts,
            model=EMBEDDING_MODEL,
            input_type=input_type,
            output_dimension=EMBEDDING_DIMENSION,
            output_dtype="float",
        )
        return [list(embedding) for embedding in response.embeddings]
