import hashlib
import math

from backend.app.config import EMBEDDING_DIMENSION
from backend.app.services.embeddings.base import BaseEmbedder


class HashEmbedder(BaseEmbedder):
    def embed_texts(self, texts: list[str], *, input_type: str) -> list[list[float]]:
        return [self._embed_single(text, input_type=input_type) for text in texts]

    def _embed_single(self, text: str, *, input_type: str) -> list[float]:
        seed_text = f"{input_type}:{text}".encode("utf-8")
        values: list[float] = []
        counter = 0
        while len(values) < EMBEDDING_DIMENSION:
            digest = hashlib.sha256(seed_text + counter.to_bytes(4, "big")).digest()
            for index in range(0, len(digest), 4):
                chunk = digest[index : index + 4]
                if len(chunk) < 4:
                    continue
                number = int.from_bytes(chunk, "big", signed=False)
                values.append((number / 2**32) * 2 - 1)
                if len(values) == EMBEDDING_DIMENSION:
                    break
            counter += 1
        norm = math.sqrt(sum(value * value for value in values)) or 1.0
        return [value / norm for value in values]
