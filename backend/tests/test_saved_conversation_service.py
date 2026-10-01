import asyncio

import pytest

from backend.app.repositories.saved_conversation_repository import SavedConversationNotFoundError
from backend.app.schemas.legal import LegalQuestionResponse
from backend.app.services.saved_conversation_service import SavedConversationService


class FakeSavedRepository:
    def __init__(self) -> None:
        self.saved: dict | None = None

    async def save_analysis(self, **kwargs) -> int:
        self.saved = kwargs
        return 71

    async def restore(self, user_id: int, conversation_id: int) -> dict:
        if (user_id, conversation_id) != (42, 71):
            raise SavedConversationNotFoundError(conversation_id)
        return {
            "conversation": {"id": 71, "user_id": 42},
            "messages": [
                {"role": "user", "content": "첫 질문"},
                {"role": "assistant", "content": "첫 답변"},
                {"role": "user", "content": "최근 질문"},
                {"role": "assistant", "content": "최근 답변"},
            ],
        }

    async def list_for_user(self, user_id: int) -> list[dict]:
        return [{"id": 71, "user_id": user_id}]

    async def restore_context(self, user_id, conversation_id):
        return await self.restore(user_id, conversation_id)

    async def delete(self, user_id: int, conversation_id: int) -> None:
        if (user_id, conversation_id) != (42, 71):
            raise SavedConversationNotFoundError(conversation_id)


def response() -> LegalQuestionResponse:
    return LegalQuestionResponse(
        request_id="req-fixed", agent_id="labor", termination_reason="model_finished",
        question_summary="요약", answer="답변", is_mock=False,
    )


def test_member_response_uses_authenticated_users_id_and_request_id() -> None:
    repository = FakeSavedRepository()
    service = SavedConversationService(repository)

    conversation_id = asyncio.run(service.save_response(
        actor={"id": 42, "role": "USER"}, category="labor",
        question="임금을 받지 못했습니다.", response=response(),
    ))

    assert conversation_id == 71
    assert repository.saved["user_id"] == 42
    assert repository.saved["execution_key"] == "req-fixed"


def test_guest_cannot_save_or_restore_a_member_conversation() -> None:
    service = SavedConversationService(FakeSavedRepository())

    with pytest.raises(PermissionError):
        asyncio.run(service.save_response(
            actor={"id": "guest", "role": "GUEST"}, category="labor",
            question="임금을 받지 못했습니다.", response=response(),
        ))
    with pytest.raises(PermissionError):
        asyncio.run(service.build_context_for_actor(
            actor={"id": "guest", "role": "GUEST"}, conversation_id=71,
        ))


def test_context_is_limited_to_first_and_recent_turns_with_character_cap() -> None:
    service = SavedConversationService(FakeSavedRepository())

    context = asyncio.run(service.build_context_for_actor(
        actor={"id": 42, "role": "USER"}, conversation_id=71, max_characters=12,
    ))

    assert context[0] == {"role": "user", "content": "첫 질문"}
    assert sum(len(item["content"]) for item in context) <= 12


def test_term_context_uses_one_owner_checked_restore_and_preserves_selection():
    class Repository(FakeSavedRepository):
        calls = 0
        async def restore(self, user_id, conversation_id):
            self.calls += 1
            restored = await super().restore(user_id, conversation_id)
            restored["conversation"]["category"] = "legal_terms"
            return restored

    repository = Repository()
    context = asyncio.run(SavedConversationService(repository).build_term_context_for_actor(
        actor={"id": 42, "role": "USER"}, conversation_id=71, max_characters=9))
    assert repository.calls == 1
    assert context == [{"role": "user", "content": "첫 질문"},
                       {"role": "assistant", "content": "첫 답변"},
                       {"role": "user", "content": "최"}]


@pytest.mark.parametrize("category", ["housing", None])
def test_term_context_rejects_other_or_missing_category(category):
    class Repository(FakeSavedRepository):
        async def restore(self, *args):
            restored = await super().restore(*args)
            restored["conversation"]["category"] = category
            return restored
    with pytest.raises(SavedConversationNotFoundError):
        asyncio.run(SavedConversationService(Repository()).build_term_context_for_actor(
            actor={"id": 42, "role": "USER"}, conversation_id=71))


def test_term_context_rejects_guest_before_query_and_other_owner():
    class Repository(FakeSavedRepository):
        calls = 0
        async def restore(self, *args):
            self.calls += 1
            return await super().restore(*args)
    repository = Repository()
    service = SavedConversationService(repository)
    with pytest.raises(PermissionError):
        asyncio.run(service.build_term_context_for_actor(
            actor={"id": "guest", "role": "GUEST"}, conversation_id=71))
    assert repository.calls == 0
    with pytest.raises(SavedConversationNotFoundError):
        asyncio.run(service.build_term_context_for_actor(
            actor={"id": 99, "role": "USER"}, conversation_id=71))


def test_term_context_wrong_category_returns_http_404_before_model_call(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.app.routers import legal_terms

    class Repository(FakeSavedRepository):
        async def restore(self, *args):
            restored = await super().restore(*args)
            restored["conversation"]["category"] = "housing"
            return restored

    async def unexpected_model(*args):
        pytest.fail("invalid conversation must not reach the model")

    monkeypatch.setattr(legal_terms, "saved_conversation_service", SavedConversationService(Repository()))
    monkeypatch.setattr(legal_terms.term_chat_service, "chat", unexpected_model)
    app = FastAPI()
    app.include_router(legal_terms.router)
    app.dependency_overrides[legal_terms.actor] = lambda: {"id": 42, "role": "USER"}
    with TestClient(app) as client:
        result = client.post("/api/legal-terms/chat", json={"message": "임금체불이 뭐예요?", "conversation_id": 71})
    assert result.status_code == 404
    assert result.json()["detail"]["code"] == "NOT_FOUND"


def test_snapshot_uses_the_numeric_contract_version_required_by_db() -> None:
    import json

    from backend.app.repositories.saved_conversation_repository import SavedConversationRepository

    assert json.loads(SavedConversationRepository._snapshot({"kind": "legal_analysis"})) == {
        "version": 1,
        "payload": {"kind": "legal_analysis"},
    }
