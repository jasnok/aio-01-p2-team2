"""Validate external search results before progress events or generation."""
from pydantic import ValidationError

from backend.app.schemas.legal import Evidence

SOURCE_TYPES = {
    "search_cases": {"case"},
    "search_laws": {"law"},
    "search_consultations": {"consultation"},
    "search_legal_documents": {"law", "case"},
}


class SearchContractError(ValueError):
    """Static errors deliberately exclude the external payload."""


def search_evidence(payload: object, tool_name: str) -> list[dict]:
    if not isinstance(payload, dict) or type(payload.get("success")) is not bool:
        raise SearchContractError("MCP 검색 응답에 boolean success가 필요합니다.")
    if not payload["success"]:
        raise RuntimeError("MCP 검색에 실패했습니다.")
    data = payload.get("data")
    if tool_name == "search_legal_documents":
        if not isinstance(data, dict):
            raise SearchContractError("MCP 통합 검색 data는 객체여야 합니다.")
        data = data.get("items")
    if not isinstance(data, list):
        raise SearchContractError("MCP 검색 근거는 배열이어야 합니다.")
    for item in data:
        if not isinstance(item, dict):
            raise SearchContractError("MCP 검색 근거 항목은 객체여야 합니다.")
        try:
            evidence = Evidence.model_validate(item)
        except ValidationError:
            raise SearchContractError("MCP 검색 근거 스키마가 올바르지 않습니다.") from None
        if evidence.source.source_type not in SOURCE_TYPES[tool_name]:
            raise SearchContractError("MCP 검색 근거의 자료 유형이 올바르지 않습니다.")
    # Retain the original evidence representation and extension metadata.
    return data
