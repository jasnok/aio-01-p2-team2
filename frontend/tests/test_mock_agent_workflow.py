import pytest

from frontend.components.evaluation_panel import run_mock_evaluation
from frontend.core.workflow import MOCK_SCENARIOS, WORKFLOW_STEPS, MockScenarioError
from frontend.services.mock_legal_service import MockLegalService


service = MockLegalService()


def test_workflow_has_expected_user_visible_order() -> None:
    assert [code for code, _ in WORKFLOW_STEPS] == [
        "validate",
        "route",
        "search_laws",
        "search_cases",
        "validate_evidence",
        "generate",
    ]


@pytest.mark.parametrize("scenario", ["backend_error", "mcp_error", "db_error", "timeout", "invalid_response", "cancelled"])
def test_mock_error_scenarios_have_actionable_error(scenario: str) -> None:
    with pytest.raises(MockScenarioError) as caught:
        service.analyze_case("labor", "퇴직금을 받지 못했습니다.", scenario=scenario)
    assert caught.value.code
    assert caught.value.stage
    assert caught.value.next_action


@pytest.mark.parametrize("scenario,state", [("no_results", "no_results"), ("no_evidence", "no_evidence")])
def test_empty_result_scenarios_do_not_invent_evidence(scenario: str, state: str) -> None:
    result = service.analyze_case("housing", "보증금 반환 자료를 확인해 주세요.", scenario=scenario)
    assert result["result_state"] == state
    assert result["related_laws"] == []
    assert result["similar_cases"] == []


def test_mock_evaluation_compares_expected_and_actual() -> None:
    rows = run_mock_evaluation(service)
    assert rows
    assert all(row["판정"] == "PASS" for row in rows)


def test_every_scenario_has_a_visible_label() -> None:
    assert set(MOCK_SCENARIOS) == {
        "success",
        "no_results",
        "no_evidence",
        "backend_error",
        "mcp_error",
        "db_error",
        "timeout",
        "invalid_response",
        "cancelled",
    }
