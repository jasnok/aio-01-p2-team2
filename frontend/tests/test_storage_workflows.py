from types import SimpleNamespace

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from frontend.clients import backend_client as api
from frontend.clients.agent_stream import final_result
from frontend.services.history_service import parse_page


RAW = dict(request_id="req", agent_id="consumer", status="completed", termination_reason="model_finished",
           question_summary="요약", answer="분석 답변", is_mock=False)


@pytest.mark.parametrize("token,selected,expected", [(None, True, False), ("token", True, True), ("token", False, False)])
def test_save_headers_and_sync_sse_agree(monkeypatch, token, selected, expected):
    calls = []
    def request(*args, **kwargs):
        calls.append(kwargs)
        return RAW
    monkeypatch.setattr(api, "_request", request)
    api.ask_legal_question("consumer", "질문입니다", "guest-id", token=token, save_selected=selected)
    api.create_agent_run(token, "guest-id", "consumer", "질문입니다", "unique", save_selected=selected)
    for call in calls:
        assert call["json"]["save_selected"] is expected
        assert ("Authorization" in call["headers"]) == bool(token)


def test_storage_metadata_survives_final_snapshot():
    raw = {**RAW, "saved": True, "conversation_id": 18, "storage": "member"}
    assert final_result(dict(run_id="r", status="completed", result=raw), "r")["saved"] is True
    with pytest.raises(api.BackendClientError):
        final_result(dict(run_id="r", status="completed", result={**raw, "saved": "true"}), "r")


def test_guest_expiry_and_bad_contract():
    page = parse_page(dict(items=[
        dict(id="a", type="analysis", expires_at="2000-01-01T00:00:00Z"),
        dict(id="b", type="legal_terms", expires_at="2099-01-01T00:00:00Z"),
    ], expires_in=60))
    assert [i["id"] for i in page["items"]] == ["b"]
    for payload in ({}, {"items": "bad"}, {"items": [{"id": 1, "type": "unknown"}]}):
        with pytest.raises(api.BackendClientError):
            parse_page(payload)


def history_app():
    return AppTest.from_string('''
import streamlit as st
from frontend.core.session import initialize_session
from frontend.components.saved_history import render_saved_history
initialize_session()
st.session_state.auth_token = "member"
render_saved_history()
''').run()


def test_history_failure_isolation_and_read_only_detail(monkeypatch):
    monkeypatch.setattr(api, "list_saved_conversations", lambda *a, **kw: {"items": [{"id": 1, "title": "내 분석"}]})
    def unavailable(*a, **kw):
        raise api.BackendClientError("아직 준비되지 않았습니다.", status_code=404)
    monkeypatch.setattr(api, "list_legal_term_conversations", unavailable)
    monkeypatch.setattr(api, "get_saved_conversation", lambda *a: dict(id=1, question="질문", result=RAW))
    app = history_app()
    assert not app.exception and app.error
    app.button(key="history-analysis-1-open").click().run()
    assert not app.exception
    assert any(x.value == "분석 답변" for x in app.markdown)
    assert not app.text_input and not app.text_area


def test_same_id_different_kind_delete_requires_confirmation(monkeypatch):
    deleted = []
    monkeypatch.setattr(api, "list_saved_conversations", lambda *a, **kw: {"items": [{"id": 1}]})
    monkeypatch.setattr(api, "list_legal_term_conversations", lambda *a, **kw: {"items": [] if deleted else [{"id": 1}]})
    monkeypatch.setattr(api, "delete_legal_term_conversation", lambda *a: deleted.append("terms"))
    monkeypatch.setattr(api, "delete_saved_conversation", lambda *a: deleted.append("analysis"))
    app = history_app()
    app.button(key="history-legal_terms-1-delete").click().run()
    assert not deleted
    app.button(key="history-legal_terms-1-yes").click().run()
    assert not app.exception and deleted == ["terms"]
    assert app.button(key="history-analysis-1-delete")


def test_auth_login_and_expiration_clear_private_state():
    app = AppTest.from_string('''
import streamlit as st
from frontend.core.session import initialize_session
from frontend.core.auth_session import apply_login, expire_session
initialize_session()
def login():
    apply_login(dict(session_token="new-token", expires_in=60, user=dict(id="u2", role="USER", display_name="사용자")))
st.button("login", on_click=login)
st.button("expire", on_click=expire_session)
''').run()
    app.session_state["last_result"] = RAW
    app.session_state["history-analysis-1-detail"] = {"secret": "old user"}
    app.session_state["terms_messages"] = [{"content": "old user"}]
    app.button[0].click().run()
    assert not app.exception and app.session_state["last_result"] is None
    assert "history-analysis-1-detail" not in app.session_state
    assert "terms_messages" not in app.session_state
    assert app.session_state["auth_token"] == "new-token"
    app.button[1].click().run()
    assert app.session_state["auth_token"] is None
    assert app.session_state["current_user"]["role"] == "GUEST"


def test_pending_run_keeps_original_save_choice(monkeypatch):
    from frontend.components import stream_analysis
    created = []
    received = []
    def create(*args, **kwargs):
        created.append(kwargs)
        return dict(run_id="one")
    def receive(*args):
        received.append(args[2])
        if len(received) == 1:
            raise api.BackendClientError("再接続", "SSE_DISCONNECTED")
        return RAW
    monkeypatch.setattr(api, "create_agent_run", create)
    monkeypatch.setattr(stream_analysis, "receive_run", receive)
    app = AppTest.from_string('''
import streamlit as st
from frontend.core.session import initialize_session
from frontend.components.stream_analysis import analyze_with_stream
initialize_session()
st.session_state.auth_token = "token"
save = st.checkbox("save", value=True)
if st.button("run"):
    try:
        st.session_state.last_result = analyze_with_stream("consumer", "질문입니다", save_selected=save)
    except ValueError:
        pass
''').run()
    app.button[0].click().run()
    app.checkbox[0].uncheck()
    app.button[0].click().run()
    assert not app.exception
    assert received == ["one", "one"]
    assert created == [{"save_selected": True}]
    assert app.session_state["last_result"]["save_requested"] is True


def test_stream_error_body_can_be_read():
    response = httpx.Response(401, stream=httpx.ByteStream(b'{"detail":{"code":"AUTH_REQUIRED","message":"expired"}}'))
    assert api._extract_api_error(response) == ("AUTH_REQUIRED", "expired")
