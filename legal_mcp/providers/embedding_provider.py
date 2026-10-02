"""검색 질의를 임베딩 벡터로 변환하는 Provider."""

import os
import hashlib
from contextlib import contextmanager
from dataclasses import dataclass
from threading import Condition
from typing import Protocol
from legal_mcp.core.cache import QueryCache

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
        api_key: str | None = None,
    ) -> None:
        api_key = api_key if api_key is not None else os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise RuntimeError("OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")

        self.model = model or os.getenv(
            "EMBEDDING_MODEL",
            "text-embedding-3-small",
        )
        self.dimension = dimension if dimension is not None else int(
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

    def close(self) -> None:
        self.client.close()


@dataclass(eq=False)
class _Lease:
    key: tuple
    provider: OpenAIEmbeddingProvider
    users: int = 0
    retired: bool = False


class EmbeddingClients:
    """Reuse the current configuration; retire old clients after their last user."""

    def __init__(self):
        self.condition = Condition()
        self.current = None
        self.entries = []
        self.closing = False

    def _dispose(self, entry):
        try:
            entry.provider.close()
        finally:
            self.entries.remove(entry)

    @contextmanager
    def acquire(self, key, model, dimension, api_key):
        with self.condition:
            if self.closing:
                raise RuntimeError("Embedding clients are shutting down")
            entry = self.current
            if entry is None or entry.key != key:
                provider = OpenAIEmbeddingProvider(model, dimension, api_key)
                old = entry
                entry = self.current = _Lease(key, provider)
                self.entries.append(entry)
                if old is not None:
                    old.retired = True
                    if not old.users:
                        self._dispose(old)
            entry.users += 1
        try:
            yield entry.provider
        finally:
            with self.condition:
                entry.users -= 1
                try:
                    if entry.retired and not entry.users:
                        self._dispose(entry)
                finally:
                    self.condition.notify_all()

    def close(self):
        with self.condition:
            if self.closing:
                self.condition.wait_for(lambda: not self.closing)
                return
            self.closing = True
            self.condition.notify_all()
            try:
                while any(entry.users for entry in self.entries):
                    self.condition.wait()
                errors = []
                for entry in list(self.entries):
                    try:
                        self._dispose(entry)
                    except Exception as error:
                        errors.append(error)
                self.current = None
                if errors:
                    raise errors[0]
            finally:
                self.closing = False
                self.condition.notify_all()


_query_cache = QueryCache()
_clients = EmbeddingClients()


def close_embedding_clients() -> None:
    """Drain and close process-local search clients at HTTP server shutdown."""
    _clients.close()


def create_embedding(text: str) -> list[float]:
    """단일 검색 질의를 1,536차원 벡터로 변환한다."""

    if not text.strip():
        raise ValueError("임베딩할 텍스트는 비어 있을 수 없습니다.")

    model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    dimension = int(os.getenv("EMBEDDING_DIMENSION", "1536"))
    api_key = os.getenv("OPENAI_API_KEY", "")
    configuration = (model, dimension, hashlib.sha256(api_key.encode()).digest())

    def load():
        with _clients.acquire(configuration, model, dimension, api_key) as provider:
            return provider.embed([text])[0]

    return _query_cache.get_or_load((text, *configuration), load, ttl=300)
