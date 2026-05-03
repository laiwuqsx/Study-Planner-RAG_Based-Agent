from backend.app.config import EMBEDDING_PROVIDER
from backend.app.services.embeddings.base import BaseEmbedder
from backend.app.services.embeddings.hash_embedder import HashEmbedder
from backend.app.services.embeddings.voyage_embedder import VoyageEmbedder


def get_embedder() -> BaseEmbedder:
    if EMBEDDING_PROVIDER == "voyage":
        return VoyageEmbedder()
    if EMBEDDING_PROVIDER == "hash":
        return HashEmbedder()
    raise ValueError(f"Unsupported embedding provider: {EMBEDDING_PROVIDER}")
