import httpx
import pytest

from frontend.clients import backend_client


def test_extract_api_error_reads_fastapi_detail() -> None:
    response = httpx.Response(
        502,
        json={"detail": {"code": "MCP_UNAVAILABLE", "message": "MCP 연결 실패"}},
    )
    assert backend_client._extract_api_error(response) == ("MCP_UNAVAILABLE", "MCP 연결 실패")


def test_ask_question_rejects_contract_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(backend_client, "_request", lambda *args, **kwargs: {"status": "completed"})
    with pytest.raises(backend_client.BackendClientError) as captured:
        backend_client.ask_legal_question("labor", "퇴직금을 받지 못했습니다", "test-session")
    assert captured.value.code == "CONTRACT_MISMATCH"


def test_auth_headers_use_token_or_guest_id() -> None:
    assert backend_client.auth_headers("token-value", "guest-1") == {"Authorization": "Bearer token-value"}
    assert backend_client.auth_headers(None, "guest-1") == {"X-Guest-Id": "guest-1"}


def test_request_accepts_empty_204_response(monkeypatch: pytest.MonkeyPatch) -> None:
    response = httpx.Response(204, request=httpx.Request("POST", "http://backend/api/auth/logout"))
    monkeypatch.setattr(httpx, "request", lambda *args, **kwargs: response)
    assert backend_client._request("POST", "/api/auth/logout") == {}


def test_admin_question_delete_sends_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    def fake_request(method, path, **kwargs):
        captured.update({"method": method, "path": path, **kwargs})
        return {}

    monkeypatch.setattr(backend_client, "_request", fake_request)
    backend_client.delete_question_api("admin-token", "unused", "question-1", "", reason="개인정보 노출")

    assert captured["method"] == "DELETE"
    assert captured["json"] == {"reason": "개인정보 노출"}


def test_owner_question_delete_sends_password_without_admin_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    def fake_request(method, path, **kwargs):
        captured.update({"method": method, "path": path, **kwargs})
        return {}

    monkeypatch.setattr(backend_client, "_request", fake_request)
    backend_client.delete_question_api(None, "guest-1", "question-1", "2468")

    assert captured["json"] == {"post_password": "2468"}


def test_agent_run_create_sends_idempotency_key(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    def fake_request(method, path, **kwargs):
        captured.update({"method": method, "path": path, **kwargs})
        return {"run_id": "run-1", "status": "QUEUED"}

    monkeypatch.setattr(backend_client, "_request", fake_request)
    result = backend_client.create_agent_run(None, "guest-1", "housing", "보증금 질문", "request-key")

    assert result["status"] == "QUEUED"
    assert captured["headers"]["Idempotency-Key"] == "request-key"


@pytest.mark.parametrize("body", ["[]", "null", '"text"', "true", "42", "<html>proxy error</html>"])
def test_request_rejects_non_object_success(monkeypatch, body):
    response = httpx.Response(200, content=body, request=httpx.Request("GET", "http://backend/history"))
    monkeypatch.setattr(httpx, "request", lambda *args, **kwargs: response)
    with pytest.raises(backend_client.BackendClientError) as caught:
        backend_client._request("GET", "/api/history")
    assert caught.value.code == "INVALID_RESPONSE"


@pytest.mark.parametrize("body", ["[]", "null", '"text"', "true", "42", "<html>proxy error</html>",
    '{"detail":{"code":[],"message":"bad"}}', '{"detail":{"code":"BAD","message":{}}}',
    '{"detail":null}', '{"detail":{"code":"","message":"bad"}}'])
def test_request_handles_malformed_error_body(monkeypatch, body):
    response = httpx.Response(502, content=body, request=httpx.Request("GET", "http://backend/history"))
    monkeypatch.setattr(httpx, "request", lambda *args, **kwargs: response)
    with pytest.raises(backend_client.BackendClientError) as caught:
        backend_client._request("GET", "/api/history")
    assert caught.value.code == "BACKEND_ERROR"
    assert caught.value.status_code == 502
    assert caught.value.user_message == "Backend 요청에 실패했습니다. HTTP 502"


@pytest.mark.parametrize("status", [401, 403, 404])
def test_access_errors_keep_status_guidance_with_malformed_body(monkeypatch, status):
    from types import SimpleNamespace
    import streamlit
    state = SimpleNamespace(auth_invalid=False)
    monkeypatch.setattr(streamlit, "session_state", state)
    response = httpx.Response(status, content="[]", request=httpx.Request("GET", "http://backend/history"))
    monkeypatch.setattr(httpx, "request", lambda *args, **kwargs: response)
    with pytest.raises(backend_client.BackendClientError) as caught:
        backend_client._request("GET", "/api/history", headers={"Authorization": "Bearer fake"})
    assert caught.value.status_code == status
    assert state.auth_invalid == (status == 401)


def test_fastapi_validation_and_plain_detail_are_preserved():
    assert backend_client._extract_api_error(httpx.Response(422, json={"detail": [{"type": "missing"}]}))[0] == "VALIDATION_ERROR"
    assert backend_client._extract_api_error(httpx.Response(409, json={"detail": "입력 충돌"})) == ("BACKEND_ERROR", "입력 충돌")


def test_valid_object_success_is_preserved(monkeypatch):
    response = httpx.Response(200, json={"items": [], "count": 0}, request=httpx.Request("GET", "http://backend/history"))
    monkeypatch.setattr(httpx, "request", lambda *args, **kwargs: response)
    assert backend_client._request("GET", "/api/history") == {"items": [], "count": 0}


@pytest.mark.parametrize("status", [200, 502])
def test_streamlit_connection_screen_shows_error_without_exception(monkeypatch, status):
    from streamlit.testing.v1 import AppTest
    response = httpx.Response(status, content="[]", request=httpx.Request("GET", "http://backend/health"))
    monkeypatch.setattr(httpx, "request", lambda *args, **kwargs: response)
    app = AppTest.from_string(
        "from frontend.components.connection_status import render_connection_status\n"
        "render_connection_status()"
    ).run(timeout=20)
    app.button[0].click().run(timeout=20)
    assert not app.exception
    assert len(app.error) == 1
    assert not app.success

