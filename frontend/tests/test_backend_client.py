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

