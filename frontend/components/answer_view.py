import streamlit as st
import re
from uuid import uuid4

from frontend.components.case_card import render_case_card
from frontend.components.law_card import render_law_card
from frontend.components.result_state import render_demo_banner, render_empty
from frontend.components.result_export import render_result_download


def _render_readable_answer(text):
    # Preserve existing Markdown structure; add paragraph breaks only to plain prose.
    if "\n" not in text and len(text) > 240:
        text = re.sub(r"(?<=[다요][.!?])\s+", "\n\n", text)
    st.markdown("""
<style>
div[class*="st-key-lawpath-answer-"] {
    border-left: 4px solid #2563eb;
    padding: 18px 22px;
    background: var(--secondary-background-color, #f5f7fb);
    border-radius: 10px;
    margin: 8px 0 20px;
}
div[class*="st-key-lawpath-answer-"] [data-testid="stMarkdownContainer"] {
    line-height: 1.85;
    overflow-wrap: anywhere;
}
div[class*="st-key-lawpath-answer-"] [data-testid="stMarkdownContainer"] p {
    line-height: 1.85;
    margin-bottom: 1em;
}
</style>
""", unsafe_allow_html=True)
    # Unique container keys also support several open saved-history answers.
    with st.container(key=f"lawpath-answer-{uuid4().hex}"):
        st.markdown("**AI 답변**")
        st.markdown(text, unsafe_allow_html=False)


def render_analysis_result(result: dict) -> None:
    if result.get("is_mock", True):
        render_demo_banner()
    st.markdown("### 분석 안내")
    state = result.get("result_state", "completed")
    assessment = result.get("input_assessment")
    message = assessment["message"] if assessment else None
    if state == "needs_clarification":
        st.warning(message or "검색을 진행하려면 추가 정보가 필요합니다.")
        if result["answer"] != message:
            _render_readable_answer(result["answer"])
        with st.expander("추가로 확인할 내용", expanded=True):
            for index, question in enumerate(dict.fromkeys(result.get("follow_up_questions", [])), 1):
                st.text(f"{index}. {question}")
        return
    if state == "no_evidence":
        st.warning("공식 근거가 부족합니다. 아래 안내는 법률 판단이 아닙니다.")
    elif state == "no_results":
        st.info("검색 결과가 없습니다. 질문에 날짜, 상대방과 요청 내용을 추가해 보세요.")
    _render_readable_answer(result["answer"])
    follow_ups = result.get("follow_up_questions", [])
    if follow_ups:
        with st.expander("추가로 확인할 내용"):
            st.caption("상황을 더 정확히 파악하기 위한 구체적인 질문입니다.")
            for index, item in enumerate(dict.fromkeys(follow_ups), 1):
                st.text(f"{index}. {item}")
    render_result_download(result)
    from frontend.components.evidence_card import render_evidence_card
    for field, heading, kind in (
        ("related_laws", "관련 법령", "law"),
        ("similar_cases", "유사 판례", "case"),
        ("consultations", "소비자원 상담사례", "consultation"),
    ):
        items = result.get(field, [])
        with st.expander(f"{heading} ({len(items)}건)", expanded=False):
            if not items:
                render_empty("표시할 자료가 없습니다.")
            for index, item in enumerate(items, 1):
                render_evidence_card(item, index, kind)
    cautions = list(dict.fromkeys(result.get("cautions", [])))
    if cautions:
        with st.container(border=True):
            st.caption("답변을 읽을 때 참고해 주세요")
            for caution in cautions:
                st.text(caution)


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

