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

