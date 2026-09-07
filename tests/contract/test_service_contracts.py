import json
from pathlib import Path

from backend.app.schemas.legal import LegalQuestionRequest, LegalQuestionResponse
from frontend.core.models import LegalQuestionView
from legal_mcp.schemas.tools import ToolResult

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_question_request_contract() -> None:
    request = LegalQuestionRequest.model_validate(load_fixture("legal_question_request.json"))
    assert request.category == "labor"


def test_backend_and_frontend_share_response_contract() -> None:
    payload = load_fixture("legal_question_response.json")
    assert LegalQuestionResponse.model_validate(payload)
    assert LegalQuestionView.model_validate(payload)


def test_mcp_tool_result_contracts() -> None:
    for name in ("search_laws_result.json", "search_cases_result.json", "get_law_article_result.json"):
        assert ToolResult.model_validate(load_fixture(name)).success is True
