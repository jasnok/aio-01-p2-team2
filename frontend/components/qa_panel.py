import streamlit as st

from frontend.core.session import reset_session, select_category
from frontend.data.mock_catalog import MOCK_CATALOG
from frontend.services.base import LegalService


def _load_scenario(category: str, service: LegalService) -> None:
    select_category(category)
    question = {
        "housing": "계약이 끝났는데 보증금을 받지 못했습니다.",
        "labor": "퇴직했는데 퇴직금을 받지 못했습니다.",
        "consumer": "돈을 보냈는데 물건을 받지 못했습니다.",
    }[category]
    result = service.analyze_case(category, question)
    st.session_state.question_message = question
    st.session_state.last_result = result
    st.session_state.session_history.append(result)


def _load_empty_state() -> None:
    st.session_state.selected_feature = "laws"
    st.session_state.law_results = []


def _load_long_text() -> None:
    st.session_state.selected_feature = "analysis"
    st.session_state.question_message = "계약과 반환 요청에 관한 상세한 사실관계를 확인하기 위한 긴 입력 예시입니다. " * 10


def render_qa_panel(service: LegalService) -> None:
    with st.sidebar:
        with st.expander("🧪 QA 빠른 테스트"):
            st.caption("개발용 화면 상태를 한 번에 불러옵니다.")
            for category in MOCK_CATALOG:
                label = {"housing": "임대차 결과", "labor": "근로 결과", "consumer": "소비자 결과"}[category]
                st.button(label, key=f"qa-{category}", on_click=_load_scenario, args=(category, service), use_container_width=True)
            st.button("결과 없음", key="qa-empty", on_click=_load_empty_state, use_container_width=True)
            st.button("긴 입력", key="qa-long", on_click=_load_long_text, use_container_width=True)
            st.button("전체 세션 초기화", key="qa-reset", on_click=reset_session, use_container_width=True)
