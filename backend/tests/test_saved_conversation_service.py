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


def test_snapshot_uses_the_numeric_contract_version_required_by_db() -> None:
    import json

    from backend.app.repositories.saved_conversation_repository import SavedConversationRepository

    assert json.loads(SavedConversationRepository._snapshot({"kind": "legal_analysis"})) == {
        "version": 1,
        "payload": {"kind": "legal_analysis"},
    }
