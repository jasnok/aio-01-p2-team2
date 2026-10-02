from frontend.components.legal_terms_chat import build_context_message
import pytest


def test_context_is_bounded_and_current_question_is_preserved():
    result = dict(question="원질문" * 500, question_summary="분석요약" * 500, answer="답변" * 500)
    question = "현재질문" * 100
    message = build_context_message(result, question, [{"role": "assistant", "content": "이전대화" * 500}])
    assert len(message) <= 1000
    assert message.endswith(question)
    assert "원질문" in message and "분석요약" in message and "이전대화" in message


def test_chat_reuses_conversation_and_preserves_analysis(monkeypatch):
    from types import SimpleNamespace
    from frontend.components import legal_terms_chat
    monkeypatch.setattr(legal_terms_chat, "get_frontend_settings", lambda: SimpleNamespace(frontend_data_mode="api"))
    from streamlit.testing.v1 import AppTest
    from frontend.clients import backend_client
    calls = []
    def chat(*args, **kwargs):
        calls.append((args, kwargs))
        return {"answer": "쉬운 설명", "conversation_id": 12, "saved": False}
    monkeypatch.setattr(backend_client, "chat_legal_terms", chat)
    app = AppTest.from_string('''
import streamlit as st
from frontend.core.session import initialize_session
from frontend.components.legal_terms_chat import render_legal_terms_chat
initialize_session()
render_legal_terms_chat(dict(request_id="one", question="보증금 반환 질문", question_summary="임대차 종료", answer="임차권 설명"))
''').run()
    for _ in range(2):
        app.text_area[0].set_value("임차권은 무엇인가요?")
        next(b for b in app.button if b.label == "질문하기").click().run()
        assert not app.exception
    assert "보증금 반환 질문" in calls[0][0][2]
    assert calls[0][1]["conversation_id"] is None
    assert calls[1][1]["conversation_id"] == 12
    assert len(app.chat_message) == 4


@pytest.mark.parametrize("fail_first_save", [False, True])
def test_save_then_followups_keep_conversation_and_new_chat_resets(monkeypatch, fail_first_save):
    from types import SimpleNamespace
    from streamlit.testing.v1 import AppTest
    from frontend.clients import backend_client
    from frontend.components import legal_terms_chat

    monkeypatch.setattr(legal_terms_chat, "get_frontend_settings", lambda: SimpleNamespace(frontend_data_mode="api"))
    calls = []
    saves = []

    def chat(*args, **kwargs):
        calls.append(kwargs["conversation_id"])
        return {"answer": "설명", "request_id": f"term-{len(calls)}",
                "conversation_id": kwargs["conversation_id"], "saved": False}

    def save(token, request_id, *, kind):
        saves.append((token, request_id, kind))
        if fail_first_save and len(saves) == 1:
            raise backend_client.BackendClientError("저장할 수 없습니다.")
        return {"saved": True, "conversation_id": 12}

    monkeypatch.setattr(backend_client, "chat_legal_terms", chat)
    monkeypatch.setattr(backend_client, "save_completed_result", save)
    app = AppTest.from_string('''
import streamlit as st
from frontend.core.session import initialize_session
from frontend.components.legal_terms_chat import render_legal_terms_chat
initialize_session()
st.session_state.auth_token = "member"
render_legal_terms_chat(dict(request_id="analysis", question="보증금 반환", answer="설명"))
''').run()

    def ask():
        app.text_area[0].set_value("임차권이 무엇인가요?")
        next(b for b in app.button if b.label == "질문하기").click().run()
        assert not app.exception

    ask()
    app.button(key="saved-action-legal_terms-term-1").click().run()
    assert not app.exception
    if fail_first_save:
        assert app.error
        assert app.session_state["terms_conversation_id"] is None
        assert app.session_state["terms_messages"][-1]["saved"] is False
        app.button(key="saved-action-legal_terms-term-1").click().run()
        assert not app.exception
    assert app.session_state["terms_conversation_id"] == 12
    assert saves == [("member", "term-1", "legal_terms")] * (2 if fail_first_save else 1)
    ask()
    ask()
    assert calls == [None, 12, 12]
    app.button(key="terms-new").click().run()
    assert app.session_state["terms_conversation_id"] is None
    assert not app.chat_message
    ask()
    assert calls[-1] is None
