import streamlit as st

from frontend.components.case_card import render_case_card
from frontend.components.law_card import render_law_card
from frontend.components.result_state import render_demo_banner, render_empty
from frontend.components.result_export import render_result_download


def render_analysis_result(result: dict) -> None:
    render_demo_banner()
    st.markdown("### 분석 안내")
    st.write(result["answer"])
    render_result_download(result)
    law_column, cases_column = st.columns([1, 2.5], gap="large")
    with law_column:
        st.markdown("### ▣ 관련 법령")
        for index, law in enumerate(result.get("related_laws", []), 1):
            render_law_card(law, index)
    with cases_column:
        st.markdown("### ⚖ 유사 판례 TOP 3")
        case_columns = st.columns(3, gap="small")
        for index, case in enumerate(result.get("similar_cases", []), 1):
            with case_columns[index - 1]:
                render_case_card(case, index)
    follow_ups = result.get("follow_up_questions", [])
    if follow_ups:
        with st.expander("추가로 확인할 내용"):
            for item in follow_ups:
                st.markdown(f"- {item}")
    st.info("\n\n".join(result.get("cautions", [])))


def render_law_results(results: list[dict] | None) -> None:
    if results is None:
        render_empty("검색어를 입력하면 관련 법령 예시를 표시합니다.")
    elif not results:
        render_empty("현재 준비된 예시 법령에서 검색 결과를 찾지 못했습니다.")
    else:
        render_demo_banner()
        for index, law in enumerate(results, 1):
            render_law_card(law, index)


def render_case_results(results: list[dict] | None) -> None:
    if results is None:
        render_empty("검색어를 입력하면 유사한 실제 사례 화면 예시를 표시합니다.")
    elif not results:
        render_empty("현재 준비된 예시 사례에서 검색 결과를 찾지 못했습니다.")
    else:
        render_demo_banner()
        columns = st.columns(min(3, len(results)), gap="large")
        for index, case in enumerate(results, 1):
            with columns[index - 1]:
                render_case_card(case, index)

