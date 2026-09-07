"""적재와 검색에서 같은 Embedding 설정을 사용하기 위한 경계."""

from typing import Protocol


class EmbeddingProvider(Protocol):
    model: str
    dimension: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...
