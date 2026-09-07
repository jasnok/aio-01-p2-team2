"""검색 질의를 임베딩 벡터로 변환하는 Provider."""

import os
from typing import Protocol

import httpx


class EmbeddingProvider(Protocol):
    model: str
    dimension: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class OllamaEmbeddingProvider:
    """Ollama의 /api/embed API를 사용하는 임베딩 Provider."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = (
            base_url
            or os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        ).rstrip("/")
        self.model = model or os.getenv(
            "EMBEDDING_MODEL",
            "nomic-embed-text",
        )
        self.timeout = timeout
        self.dimension = int(os.getenv("EMBEDDING_DIMENSION", "768"))

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        response = httpx.post(
            f"{self.base_url}/api/embed",
            json={
                "model": self.model,
                "input": texts,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()

        embeddings = response.json().get("embeddings")

        if not isinstance(embeddings, list) or len(embeddings) != len(texts):
            raise ValueError("Ollama 임베딩 응답 형식이 올바르지 않습니다.")

        return embeddings


def create_embedding(text: str) -> list[float]:
    """단일 검색 질의를 벡터로 변환한다."""
    provider = OllamaEmbeddingProvider()
    return provider.embed([text])[0]