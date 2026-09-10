from __future__ import annotations

import json
from typing import Any

from backend.app.repositories.saved_conversation_repository import SavedConversationRepository
from backend.app.schemas.legal import LegalQuestionResponse


class SavedConversationService:
    def __init__(self, repository: SavedConversationRepository | None = None) -> None:
        self.repository = repository or SavedConversationRepository()

    async def save_run(self, actor: dict, run: dict) -> int:
        if actor.get("role") == "GUEST":
            raise PermissionError("AUTH_REQUIRED")
        if run.get("status") not in {"completed", "stopped"} or not run.get("result"):
            raise ValueError("RUN_NOT_FINISHED")
        return await self.repository.save_analysis(
            user_id=int(actor["id"]),
            category=run["category"],
            question=run["question"],
            result=run["result"],
            execution_key=run["run_id"],
        )

    async def save_response(
        self,
        *,
        actor: dict,
        category: str,
        question: str,
        response: LegalQuestionResponse,
    ) -> int:
        """Persist only an explicitly saved, completed response for a member."""
        if actor.get("role") == "GUEST":
            raise PermissionError("AUTH_REQUIRED")
        if response.status not in {"completed", "stopped"}:
            raise ValueError("RUN_NOT_FINISHED")
        return await self.repository.save_analysis(
            user_id=int(actor["id"]),
            category=category,
            question=question,
            result=response.model_dump(mode="json"),
            execution_key=response.request_id,
        )

    async def build_context_for_actor(
        self,
        *,
        actor: dict,
        conversation_id: int,
        max_characters: int = 3000,
    ) -> list[dict[str, str]]:
        if actor.get("role") == "GUEST":
            raise PermissionError("AUTH_REQUIRED")
        restored = await self.repository.restore(int(actor["id"]), conversation_id)
        selected: list[dict[str, str]] = []
        messages = restored["messages"]
        first_user = next((item for item in messages if item["role"] == "user"), None)
        if first_user:
            selected.append({"role": "user", "content": first_user["content"]})
        for item in messages[-3:]:
            candidate = {"role": item["role"], "content": item["content"]}
            if candidate not in selected:
                selected.append(candidate)

        context: list[dict[str, str]] = []
        remaining = max_characters
        for item in selected:
            if remaining <= 0:
                break
            context.append({**item, "content": item["content"][:remaining]})
            remaining -= len(context[-1]["content"])
        return context

    async def save_term_chat(
        self,
        *,
        actor: dict,
        question: str,
        answer: str,
        request_id: str,
        conversation_id: int | None,
    ) -> int:
        if actor.get("role") == "GUEST":
            raise PermissionError("AUTH_REQUIRED")
        return await self.repository.save_term_chat(
            user_id=int(actor["id"]), question=question, answer=answer,
            execution_key=request_id, conversation_id=conversation_id,
        )

    async def build_term_context_for_actor(
        self, *, actor: dict, conversation_id: int, max_characters: int = 3000,
    ) -> list[dict[str, str]]:
        if actor.get("role") == "GUEST":
            raise PermissionError("AUTH_REQUIRED")
        restored = await self.repository.restore(int(actor["id"]), conversation_id)
        if restored["conversation"].get("category") != "legal_terms":
            raise SavedConversationNotFoundError(conversation_id)
        return await self.build_context_for_actor(
            actor=actor, conversation_id=conversation_id, max_characters=max_characters,
        )

    async def list_for_actor(self, actor: dict) -> list[dict[str, Any]]:
        if actor.get("role") == "GUEST":
            raise PermissionError("AUTH_REQUIRED")
        return await self.repository.list_for_user(int(actor["id"]))

    async def list_history_for_actor(
        self, *, actor: dict, page: int, page_size: int,
    ) -> tuple[list[dict[str, Any]], int]:
        if actor.get("role") == "GUEST":
            raise PermissionError("AUTH_REQUIRED")
        rows, total = await self.repository.list_history_page(
            user_id=int(actor["id"]), page=page, page_size=page_size,
        )
        return [self._history_item(row) for row in rows], total

    async def restore_for_actor(self, actor: dict, conversation_id: int) -> dict[str, Any]:
        if actor.get("role") == "GUEST":
            raise PermissionError("AUTH_REQUIRED")
        return await self.repository.restore(int(actor["id"]), conversation_id)

    async def restore_history_for_actor(self, actor: dict, conversation_id: int) -> dict[str, Any]:
        if actor.get("role") == "GUEST":
            raise PermissionError("AUTH_REQUIRED")
        restored = await self.repository.restore(int(actor["id"]), conversation_id)
        conversation = restored["conversation"]
        messages = restored["messages"]
        first_question = next((item["content"] for item in messages if item["role"] == "user"), "")
        last_answer = next((item for item in reversed(messages) if item["role"] == "assistant"), None)
        record = self._history_item({
            **conversation,
            "question": first_question,
            "answer": last_answer["content"] if last_answer else "",
            "assistant_snapshot": last_answer.get("snapshot") if last_answer else None,
        })
        if record["type"] == "analysis":
            payload = self._snapshot_payload(last_answer.get("snapshot") if last_answer else None)
            record["result"] = payload or {"answer": record["summary"]}
        else:
            record["messages"] = [
                {"role": item["role"], "content": item["content"], "created_at": item["created_at"]}
                for item in messages
            ]
        return record

    async def delete_for_actor(self, actor: dict, conversation_id: int) -> None:
        if actor.get("role") == "GUEST":
            raise PermissionError("AUTH_REQUIRED")
        await self.repository.delete(int(actor["id"]), conversation_id)

    @classmethod
    def _history_item(cls, row: dict[str, Any]) -> dict[str, Any]:
        item_type = "legal_terms" if row.get("category") == "legal_terms" else "analysis"
        payload = cls._snapshot_payload(row.get("assistant_snapshot"))
        answer = str(row.get("answer") or "")
        summary = "용어 설명" if item_type == "legal_terms" else str(
            payload.get("question_summary") or payload.get("answer") or answer
        )[:300]
        return {
            "id": int(row["id"]),
            "type": item_type,
            "title": row.get("title") or "",
            "question": row.get("question") or "",
            "summary": summary,
            "created_at": row["created_at"],
        }

    @staticmethod
    def _snapshot_payload(snapshot: Any) -> dict[str, Any]:
        if isinstance(snapshot, str):
            try:
                snapshot = json.loads(snapshot)
            except json.JSONDecodeError:
                return {}
        if not isinstance(snapshot, dict):
            return {}
        payload = snapshot.get("payload")
        return payload if isinstance(payload, dict) else {}
