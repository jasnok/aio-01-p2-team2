from __future__ import annotations

import asyncio
import json
from time import monotonic
from typing import Any

from backend.app.core.config import get_settings
from backend.app.services.session_service import SessionStoreUnavailableError, sessions


class LegalTermRunNotFoundError(LookupError):
    pass


class LegalTermRunForbiddenError(PermissionError):
    pass


class LegalTermRunStore:
    """Short-lived server-side answers used by the post-answer save button."""

    def __init__(self) -> None:
        self._memory: dict[str, tuple[dict[str, Any], float]] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _key(request_id: str) -> str:
        return f"lawpath:legal-term-run:{request_id}"

    async def remember(self, *, actor: dict, request_id: str, question: str, answer: str, conversation_id: int | None) -> None:
        record = {
            "owner_id": str(actor["id"]), "owner_role": actor["role"],
            "request_id": request_id, "question": question, "answer": answer,
            "conversation_id": conversation_id,
        }
        settings = get_settings()
        if settings.redis_enabled:
            try:
                client = await sessions._redis_client()
                await client.set(self._key(request_id), json.dumps(record, ensure_ascii=False), ex=settings.term_run_ttl_seconds)
                return
            except Exception as error:
                raise SessionStoreUnavailableError() from error
        async with self._lock:
            self._memory[request_id] = (record, monotonic() + settings.term_run_ttl_seconds)

    async def get_for_actor(self, request_id: str, actor: dict) -> dict[str, Any]:
        settings = get_settings()
        if settings.redis_enabled:
            try:
                client = await sessions._redis_client()
                raw = await client.get(self._key(request_id))
            except Exception as error:
                raise SessionStoreUnavailableError() from error
            record = json.loads(raw) if raw else None
        else:
            async with self._lock:
                entry = self._memory.get(request_id)
                if not entry or entry[1] <= monotonic():
                    self._memory.pop(request_id, None)
                    record = None
                else:
                    record = entry[0]
        if not record:
            raise LegalTermRunNotFoundError(request_id)
        if record["owner_id"] != str(actor["id"]):
            raise LegalTermRunForbiddenError(request_id)
        return record


legal_term_runs = LegalTermRunStore()
