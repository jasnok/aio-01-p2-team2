from __future__ import annotations

import asyncio
import json
from time import monotonic
from typing import Any

from backend.app.core.config import get_settings
from backend.app.services.session_service import SessionStoreUnavailableError, sessions


class GuestSessionService:
    """TTL-bound guest analysis history. It never creates a DB user row."""

    def __init__(self) -> None:
        self._memory: dict[str, tuple[list[dict[str, Any]], float]] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _key(guest_id: str) -> str:
        return f"lawpath:guest:{guest_id}:analyses"

    async def save_analysis(self, guest_id: str, run: dict[str, Any]) -> int:
        return await self._save_record(guest_id, {"kind": "legal_analysis", **run})

    async def save_term_chat(self, guest_id: str, record: dict[str, Any]) -> int:
        return await self._save_record(guest_id, {"kind": "legal_term_chat", **record})

    async def _save_record(self, guest_id: str, run: dict[str, Any]) -> int:
        ttl = get_settings().guest_session_ttl_seconds
        record = {
            "kind": run.get("kind", "legal_analysis"),
            "run_id": run["run_id"],
            "category": run.get("category"),
            "question": run["question"],
            "status": run["status"],
            "result": run.get("result"),
            "updated_at": run.get("updated_at"),
        }
        if get_settings().redis_enabled:
            try:
                client = await sessions._redis_client()
                raw = await client.get(self._key(guest_id))
                records = json.loads(raw) if raw else []
                records = [item for item in records if item["run_id"] != record["run_id"]]
                records.insert(0, record)
                await client.set(self._key(guest_id), json.dumps(records, ensure_ascii=False), ex=ttl)
            except Exception as error:
                raise SessionStoreUnavailableError() from error
            return ttl

        # Local development fallback: process-bound and explicitly non-durable.
        async with self._lock:
            records, expires_at = self._memory.get(guest_id, ([], 0.0))
            if expires_at <= monotonic():
                records = []
            records = [item for item in records if item["run_id"] != record["run_id"]]
            records.insert(0, record)
            self._memory[guest_id] = (records, monotonic() + ttl)
        return ttl

    async def list_analyses(self, guest_id: str) -> tuple[list[dict[str, Any]], int]:
        ttl = get_settings().guest_session_ttl_seconds
        if get_settings().redis_enabled:
            try:
                client = await sessions._redis_client()
                raw = await client.get(self._key(guest_id))
                remaining = await client.ttl(self._key(guest_id))
            except Exception as error:
                raise SessionStoreUnavailableError() from error
            return (json.loads(raw) if raw else [], max(0, int(remaining)))

        async with self._lock:
            entry = self._memory.get(guest_id)
            if not entry or entry[1] <= monotonic():
                self._memory.pop(guest_id, None)
                return [], 0
            return entry[0].copy(), min(ttl, max(0, int(entry[1] - monotonic())))

    async def term_context(self, guest_id: str, max_characters: int = 3000) -> list[dict[str, str]]:
        records, _ = await self.list_analyses(guest_id)
        turns: list[dict[str, str]] = []
        for record in reversed(records):
            if record.get("kind") != "legal_term_chat":
                continue
            turns.append({"role": "user", "content": str(record.get("question", ""))})
            answer = (record.get("result") or {}).get("answer", "")
            turns.append({"role": "assistant", "content": str(answer)})
        turns = turns[-6:]
        context: list[dict[str, str]] = []
        remaining = max_characters
        for turn in turns:
            if remaining <= 0:
                break
            content = turn["content"][:remaining]
            context.append({"role": turn["role"], "content": content})
            remaining -= len(content)
        return context

    async def clear(self, guest_id: str) -> None:
        if get_settings().redis_enabled:
            try:
                client = await sessions._redis_client()
                await client.delete(self._key(guest_id))
            except Exception as error:
                raise SessionStoreUnavailableError() from error
            return
        async with self._lock:
            self._memory.pop(guest_id, None)


guest_sessions = GuestSessionService()
