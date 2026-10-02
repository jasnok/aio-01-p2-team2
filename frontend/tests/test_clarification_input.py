from types import SimpleNamespace
import pytest

from streamlit.testing.v1 import AppTest

from frontend.components import follow_up_chat


def clarification_app():
    return AppTest.from_string('''
import streamlit as st
from frontend.core.session import initialize_session
from frontend.components.follow_up_chat import render_follow_up_chat
initialize_session()
st.session_state.setdefault("last_result", None)
if st.session_state.last_result is None:
    st.session_state.last_result = dict(request_id="original", question="퇴직금을 받지 못했습니다.",
        agent_id="labor", answer="근무 기간을 알려주세요.", result_state="needs_clarification")
render_follow_up_chat(st.session_state.last_result, None)
''').run()


def test_failed_clarification_keeps_input_and_explicit_retry_clears_after_success(monkeypatch):
    monkeypatch.setattr(follow_up_chat, "get_frontend_settings", lambda: SimpleNamespace(
        frontend_data_mode="api", frontend_sse_enabled=True))
    calls = []

    def analyze(category, question):
        calls.append((category, question))
        if len(calls) == 1:
            raise ValueError("연결을 확인하지 못했습니다.")
        return dict(request_id="next", question=question, agent_id=category,
                    answer="퇴직 날짜도 알려주세요.", result_state="needs_clarification")

    monkeypatch.setattr(follow_up_chat, "analyze_with_stream", analyze)
    app = clarification_app()
    # Browser form protocol must preserve drafts until a successful result.
    assert app.get("form")[0].proto.form.clear_on_submit is False
    draft = "1년 3개월 근무했습니다."
    app.text_input(key="follow_up_input").set_value(draft)
    next(b for b in app.button if b.label == "추가 정보로 다시 분석").click().run()
    assert not app.exception and app.error
    assert app.text_input(key="follow_up_input").value == draft
    assert app.session_state["last_result"]["request_id"] == "original"
    assert not app.session_state["conversation_messages"]
    next(b for b in app.button if b.label == "추가 정보로 다시 분석").click().run()
    assert not app.exception
    assert calls == [("labor", "퇴직금을 받지 못했습니다.\n추가 정보: " + draft)] * 2
    assert app.session_state["last_result"]["request_id"] == "next"
    assert app.text_input(key="follow_up_input").value == ""
    assert len(app.session_state["conversation_messages"]) == 2


@pytest.mark.parametrize("draft", ["짧음", "추가 정보" * 500])
def test_invalid_clarification_keeps_draft_without_call(monkeypatch, draft):
    monkeypatch.setattr(follow_up_chat, "analyze_with_stream", lambda *args: pytest.fail(
        "invalid input must not start analysis"))
    app = clarification_app()
    app.text_input(key="follow_up_input").set_value(draft)
    next(b for b in app.button if b.label == "추가 정보로 다시 분석").click().run()
    assert not app.exception and app.warning
    assert app.text_input(key="follow_up_input").value == draft
    assert app.session_state["last_result"]["request_id"] == "original"


def test_new_analysis_clears_draft_and_pending_recovery_state():
    app = clarification_app()
    app.text_input(key="follow_up_input").set_value("1년 3개월 근무했습니다.").run()
    app.session_state["sse_pending"] = {"run_id": "pending"}
    app.session_state["follow_up_clear_input"] = True
    app.button(key="new-analysis").click().run()
    assert not app.exception
    assert app.text_input(key="follow_up_input").value == ""
    assert "sse_pending" not in app.session_state
    assert "follow_up_clear_input" not in app.session_state
