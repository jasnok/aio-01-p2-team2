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

