from __future__ import annotations

import asyncio
import json
import secrets
from dataclasses import dataclass
from datetime import timedelta
from time import monotonic

from backend.app.core.config import get_settings


class SessionStoreUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class SessionRecord:
    user_id: int


class SessionService:
    """Opaque login tokens backed by Redis when configured, otherwise process memory."""

    def __init__(self) -> None:
        self._memory: dict[str, tuple[SessionRecord, float]] = {}
        self._lock = asyncio.Lock()
        self._redis = None

    async def issue(self, user_id: int) -> tuple[str, int]:
        settings = get_settings()
        ttl = settings.auth_session_ttl_seconds
        token = secrets.token_urlsafe(32)
        if settings.redis_enabled:
            client = await self._redis_client()
            try:
                await client.set(
                    f"lawpath:auth:{token}",
                    json.dumps({"user_id": user_id}),
                    ex=ttl,
                )
            except Exception as error:
                raise SessionStoreUnavailableError() from error
        else:
            async with self._lock:
                self._memory[token] = (SessionRecord(user_id), monotonic() + ttl)
        return token, ttl

    async def read(self, token: str | None) -> SessionRecord | None:
        if not token:
            return None
        settings = get_settings()
        if settings.redis_enabled:
            client = await self._redis_client()
            try:
                raw = await client.get(f"lawpath:auth:{token}")
            except Exception as error:
                raise SessionStoreUnavailableError() from error
            if not raw:
                return None
            return SessionRecord(int(json.loads(raw)["user_id"]))
        async with self._lock:
            entry = self._memory.get(token)
            if not entry or entry[1] <= monotonic():
                self._memory.pop(token, None)
                return None
            return entry[0]

    async def revoke(self, token: str | None) -> bool:
        if not token:
            return False
        settings = get_settings()
        if settings.redis_enabled:
            client = await self._redis_client()
            try:
                return bool(await client.delete(f"lawpath:auth:{token}"))
            except Exception as error:
                raise SessionStoreUnavailableError() from error
        async with self._lock:
            return self._memory.pop(token, None) is not None

    async def _redis_client(self):
        if self._redis is None:
            try:
                from redis.asyncio import Redis

                self._redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
            except Exception as error:
                raise SessionStoreUnavailableError() from error
        return self._redis


sessions = SessionService()
