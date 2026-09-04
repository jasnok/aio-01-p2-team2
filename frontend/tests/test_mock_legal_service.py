import pytest

from frontend.services.mock_legal_service import MockLegalService


service = MockLegalService()


def test_analyze_case_returns_selected_category_only() -> None:
    result = service.analyze_case("labor", "퇴직금을 받지 못했습니다.")
    assert result["agent_id"] == "labor"
    assert result["is_mock"] is True
    assert result["related_laws"]
    assert result["similar_cases"]


def test_law_search_filters_by_keyword() -> None:
    results = service.search_laws("housing", "보증금")
    assert results
    assert all("보증금" in item["keywords"] for item in results)


def test_case_search_returns_empty_for_unknown_keyword() -> None:
    assert service.search_cases("consumer", "존재하지않는검색어") == []


@pytest.mark.parametrize("question", ["", "짧음"])
def test_analysis_rejects_short_question(question: str) -> None:
    with pytest.raises(ValueError):
        service.analyze_case("housing", question)


def test_unknown_category_is_rejected() -> None:
    with pytest.raises(ValueError):
        service.search_laws("criminal", "검색어")


def test_term_search_filters_name_and_description() -> None:
    assert service.search_terms("housing", "내용증명")[0][0] == "내용증명"
    assert service.search_terms("housing", "없는용어") == []
