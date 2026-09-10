"""세 개별 검색 화면. MCP 응답은 Backend Client에서 검증한다."""

import streamlit as st

from frontend.components.case_card import render_case_card
from frontend.components.law_card import render_law_card
from frontend.components.search_forms import render_search_form
from frontend.core.config import get_frontend_settings
from frontend.services.base import LegalService


def render_consultation_card(item: dict, index: int) -> None:
    from frontend.components.evidence_card import render_evidence_card
    render_evidence_card(item, index, "consultation")


def render_search_page(category: str, kind: str, service: LegalService) -> None:
    result_key, method, renderer = {
        "laws": ("law_results", service.search_laws, render_law_card),
        "consultations": ("consultation_results", service.search_consultations, render_consultation_card),
        "cases": ("case_results", service.search_cases, render_case_card),
    }[kind]
    query = render_search_form(kind)
    if query is not None:
        st.session_state[result_key] = None
        st.session_state.search_errors.pop(kind, None)
        if query:
            try:
                with st.spinner("선택한 분야의 자료를 검색하고 있습니다."):
                    st.session_state[result_key] = method(category, query)
            except ValueError as error:
                st.session_state.search_errors[kind] = str(error)
    error = st.session_state.search_errors.get(kind)
    if error:
        st.error(error)
        return
    results = st.session_state[result_key]
    if results is None:
        st.info("검색어를 입력해 주세요.")
    elif not results:
        st.info("해당 분야에서 검색된 자료가 없습니다.")
    else:
        if get_frontend_settings().frontend_data_mode.lower() == "mock":
            st.warning("DEMO MODE · 화면 확인용 예시 자료입니다.")
        st.caption(f"검색 결과 {len(results)}건")
        for index, item in enumerate(results, 1):
            renderer(item, index)
