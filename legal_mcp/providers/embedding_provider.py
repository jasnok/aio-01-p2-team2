"""검색 질의를 임베딩 벡터로 변환하는 Provider."""

import os
import hashlib
from collections import OrderedDict
from threading import Lock
from time import monotonic
from typing import Protocol

from openai import OpenAI


class EmbeddingProvider(Protocol):
    model: str
    dimension: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class OpenAIEmbeddingProvider:
    """OpenAI Embeddings API를 사용하는 Provider."""

    def __init__(
        self,
        model: str | None = None,
        dimension: int | None = None,
    ) -> None:
        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise RuntimeError("OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")

        self.model = model or os.getenv(
            "EMBEDDING_MODEL",
            "text-embedding-3-small",
        )
        self.dimension = dimension or int(
            os.getenv("EMBEDDING_DIMENSION", "1536")
        )
        self.client = OpenAI(api_key=api_key, timeout=20, max_retries=1)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        response = self.client.embeddings.create(
            model=self.model,
            input=texts,
            encoding_format="float",
        )

        embeddings = [
            list(item.embedding)
            for item in sorted(response.data, key=lambda item: item.index)
        ]

        if any(len(embedding) != self.dimension for embedding in embeddings):
            raise ValueError(
                f"임베딩 차원이 DB 설정과 다릅니다. "
                f"expected={self.dimension}"
            )

        return embeddings


_query_cache: OrderedDict[tuple, tuple[float, list[float]]] = OrderedDict()
_cache_lock = Lock()


def create_embedding(text: str) -> list[float]:
    """단일 검색 질의를 1,536차원 벡터로 변환한다."""

    if not text.strip():
        raise ValueError("임베딩할 텍스트는 비어 있을 수 없습니다.")

    key = (text, os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
           os.getenv("EMBEDDING_DIMENSION", "1536"),
           hashlib.sha256(os.getenv("OPENAI_API_KEY", "").encode()).digest())
    with _cache_lock:
        entry = _query_cache.get(key)
        if entry and entry[0] > monotonic():
            _query_cache.move_to_end(key)
            return entry[1].copy()
    vector = OpenAIEmbeddingProvider().embed([text])[0]
    with _cache_lock:
        _query_cache[key] = (monotonic() + 300, vector.copy())
        _query_cache.move_to_end(key)
        while len(_query_cache) > 128:
            _query_cache.popitem(last=False)
    return vector
