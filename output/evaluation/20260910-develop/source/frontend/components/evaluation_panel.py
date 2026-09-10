import streamlit as st

from frontend.core.workflow import MockScenarioError
from frontend.services.base import LegalService


EVALUATION_CASES = (
    ("정상 퇴직금 질문", "labor", "퇴직했는데 퇴직금을 받지 못했습니다.", "success", "completed"),
    ("정상 임대차 질문", "housing", "계약이 끝났는데 보증금을 받지 못했습니다.", "success", "completed"),
    ("근거 부족", "consumer", "거래 문제의 근거를 확인하고 싶습니다.", "no_evidence", "no_evidence"),
    ("MCP 오류", "labor", "퇴직금 관련 판례를 찾아주세요.", "mcp_error", "MCP_UNAVAILABLE"),
    ("시간 초과", "housing", "보증금 반환 내용을 확인해 주세요.", "timeout", "REQUEST_TIMEOUT"),
)


def run_mock_evaluation(service: LegalService) -> list[dict]:
    rows = []
    for name, category, question, scenario, expected in EVALUATION_CASES:
        try:
            result = service.analyze_case(category, question, scenario=scenario)
            actual = result.get("result_state", result.get("status"))
        except MockScenarioError as error:
            actual = error.code
        rows.append({"테스트": name, "예상 결과": expected, "실제 결과": actual, "판정": "PASS" if actual == expected else "FAIL"})
    return rows


def render_evaluation_panel(service: LegalService) -> None:
    st.markdown("#### 📋 Agent Mock 평가")
    st.caption("예상 결과와 실제 결과를 비교합니다.")
    if st.button("대표 시나리오 평가 실행", key="run-agent-evaluation", use_container_width=True):
        st.session_state.evaluation_results = run_mock_evaluation(service)
    if st.session_state.evaluation_results:
        st.dataframe(st.session_state.evaluation_results, use_container_width=True, hide_index=True)
