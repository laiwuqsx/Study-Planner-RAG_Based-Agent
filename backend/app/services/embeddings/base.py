from abc import ABC, abstractmethod


class BaseEmbedder(ABC):
    @abstractmethod
    def embed_texts(self, texts: list[str], *, input_type: str) -> list[list[float]]:
        raise NotImplementedError
