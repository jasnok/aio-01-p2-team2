import html

import streamlit as st


def render_analysis_summary(result: dict | None) -> None:
    if not result:
        st.markdown('<div class="summary-box"><h3>▣ AI가 정리한 상황 요약</h3><p>사례를 입력하면 상황과 핵심 쟁점을 이곳에 정리합니다.</p></div>', unsafe_allow_html=True)
        return
    summary = html.escape(result["question_summary"])
    chips = "".join(f'<span class="issue-chip">{html.escape(issue)}</span>' for issue in result["key_issues"])
    st.markdown(f'<div class="summary-box"><h3>▣ AI가 정리한 상황 요약</h3><p>{summary}</p><strong>핵심 쟁점</strong><div>{chips}</div></div>', unsafe_allow_html=True)
