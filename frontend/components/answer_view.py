import streamlit as st

from frontend.components.case_card import render_case_card
from frontend.components.law_card import render_law_card
from frontend.components.result_state import render_demo_banner, render_empty
from frontend.components.result_export import render_result_download


def render_analysis_result(result: dict) -> None:
    if result.get("is_mock", True):
        render_demo_banner()
    st.markdown("### 분석 안내")
    state = result.get("result_state", "completed")
    if state == "needs_clarification":
        st.warning("검색을 진행하려면 추가 정보가 필요합니다.")
        st.write(result["answer"])
        for question in result.get("follow_up_questions", []):
            st.write(question)
        return
    if state == "no_evidence":
        st.warning("공식 근거가 부족합니다. 아래 안내는 법률 판단이 아닙니다.")
    elif state == "no_results":
        st.info("검색 결과가 없습니다. 질문에 날짜, 상대방과 요청 내용을 추가해 보세요.")
    st.write(result["answer"])
    render_result_download(result)
    from frontend.components.evidence_card import render_evidence_card
    for field, heading, kind in (
        ("related_laws", "관련 법령", "law"),
        ("similar_cases", "유사 판례", "case"),
        ("consultations", "소비자원 상담사례", "consultation"),
    ):
        st.markdown(f"### {heading}")
        items = result.get(field, [])
        if not items:
            render_empty("표시할 자료가 없습니다.")
        for index, item in enumerate(items, 1):
            render_evidence_card(item, index, kind)
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

