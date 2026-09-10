import asyncio

from backend.app.services import legal_term_chat_service
from backend.app.services.guest_session_service import GuestSessionService
from backend.app.services.legal_term_chat_service import LegalTermChatService
from backend.app.services.saved_conversation_service import SavedConversationService


def llm_settings():
    return type("Settings", (), {"llm_provider": "openai"})()


def mock_settings():
    return type("Settings", (), {"llm_provider": "mock"})()


def guest_settings():
    return type("Settings", (), {"redis_enabled": False, "guest_session_ttl_seconds": 3600})()


def test_term_chat_uses_legal_term_persona_and_structured_output(monkeypatch) -> None:
    class Provider:
        def generate_structured(self, system_prompt, message, schema):
            assert "법률 용어" in system_prompt
            assert "임금체불" in message
            return type("Result", (), {"output": {
                "is_legal_term_question": True,
                "answer": "임금체불은 약속한 날에 임금을 주지 않는 것입니다.",
                "related_terms": ["체불임금"],
                "caution": "일반 정보입니다.",
            }})()

    monkeypatch.setattr(legal_term_chat_service, "get_settings", llm_settings)
    monkeypatch.setattr(legal_term_chat_service, "get_provider", lambda _name: Provider())

    result = asyncio.run(LegalTermChatService().chat("임금체불이 무슨 뜻인가요?", []))

    assert result.is_llm_response is True
    assert result.related_terms == ["체불임금"]
    assert result.saved is False


def test_non_term_question_is_redirected_without_a_case_judgment(monkeypatch) -> None:
    class Provider:
        def generate_structured(self, *_args):
            return type("Result", (), {"output": {
                "is_legal_term_question": False,
                "answer": "승소할 수 있습니다.",
                "caution": "일반 정보입니다.",
            }})()

    monkeypatch.setattr(legal_term_chat_service, "get_settings", llm_settings)
    monkeypatch.setattr(legal_term_chat_service, "get_provider", lambda _name: Provider())

    result = asyncio.run(LegalTermChatService().chat("제가 이길 수 있나요?", []))

    assert "법률 용어" in result.answer
    assert "승소" not in result.answer


def test_mock_provider_does_not_claim_to_have_generated_an_llm_answer(monkeypatch) -> None:
    monkeypatch.setattr(legal_term_chat_service, "get_settings", mock_settings)
    result = asyncio.run(LegalTermChatService().chat("임금체불이 뭐예요?", []))
    assert result.is_llm_response is False


def test_member_term_chat_saves_using_authenticated_users_id() -> None:
    class Repository:
        async def save_term_chat(self, **kwargs):
            assert kwargs["user_id"] == 42
            assert kwargs["conversation_id"] is None
            return 18

    result = asyncio.run(SavedConversationService(Repository()).save_term_chat(
        actor={"id": 42, "role": "USER"}, question="임금체불", answer="설명",
        request_id="term-1", conversation_id=None,
    ))
    assert result == 18


def test_guest_term_context_is_temporary_and_limited(monkeypatch) -> None:
    from backend.app.services import guest_session_service

    monkeypatch.setattr(guest_session_service, "get_settings", guest_settings)
    service = GuestSessionService()
    asyncio.run(service.save_term_chat("guest-1", {
        "run_id": "term-1", "question": "임금체불", "status": "completed",
        "result": {"answer": "임금을 주지 않은 상태"},
    }))

    context = asyncio.run(service.term_context("guest-1"))
    assert context == [
        {"role": "user", "content": "임금체불"},
        {"role": "assistant", "content": "임금을 주지 않은 상태"},
    ]
