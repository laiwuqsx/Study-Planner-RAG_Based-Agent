from abc import ABC, abstractmethod


class BaseRetriever(ABC):
    @abstractmethod
    def index_document(self, *, document_id: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def delete_document(self, *, user_id: int, document_id: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def search(self, *, query: str, user_id: int, course_id: int, top_k: int, retrieval_mode: str) -> list[dict]:
        raise NotImplementedError
