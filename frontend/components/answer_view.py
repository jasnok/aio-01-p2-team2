from typing import Any

import streamlit as st


def render_answer(result: dict[str, Any]) -> None:
    st.divider()
    if result.get("is_mock"):
        st.warning("MOCK DATA — 서버 연결 검증용이며 실제 법률 자료가 아닙니다.")

    st.subheader("상황 요약")
    st.write(result.get("question_summary") or "상황 요약이 제공되지 않았습니다.")

    st.subheader("답변")
    st.write(result.get("answer") or "답변이 제공되지 않았습니다.")

    laws = result.get("laws") or []
    cases = result.get("cases") or []
    law_column, case_column = st.columns(2)
    with law_column:
        _render_documents("관련 법령", laws, "관련 법령을 찾지 못했습니다.")
    with case_column:
        _render_documents("유사 사례", cases, "유사 사례를 찾지 못했습니다.")

    follow_up_questions = result.get("follow_up_questions") or []
    if follow_up_questions:
        st.subheader("추가로 확인할 내용")
        for question in follow_up_questions:
            st.markdown(f"- {question}")

    st.info(result.get("disclaimer") or "이 답변은 법률 자문이 아닌 정보 제공입니다.")
    with st.expander("Agent 실행 Trace", expanded=False):
        trace = result.get("trace") or []
        if trace:
            st.json(trace)
        else:
            st.caption("표시할 Trace가 없습니다.")


def _render_documents(title: str, documents: list[dict[str, Any]], empty_message: str) -> None:
    st.subheader(title)
    if not documents:
        st.caption(empty_message)
        return

    for document in documents:
        with st.container(border=True):
            document_type = document.get("document_type", "DOCUMENT")
            st.caption(document_type)
            st.markdown(f"**{document.get('title', '제목 없음')}**")
            st.write(document.get("summary") or "요약이 없습니다.")
            source_name = document.get("source_name") or "출처 미상"
            source_url = document.get("source_url")
            if source_url:
                st.markdown(f"출처: [{source_name}]({source_url})")
            else:
                st.caption(f"출처: {source_name}")
            if document.get("effective_date"):
                st.caption(f"기준일: {document['effective_date']}")
            st.caption(f"문서 ID: {document.get('document_id', '-')}")

