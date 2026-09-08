import streamlit as st
from frontend.core.config import get_frontend_settings


def render_search_form(kind: str) -> str | None:
    title, key, icon = {
        "laws": ("법 검색", "law_query", "⌕"),
        "consultations": ("실제 사례 검색", "consultation_query", "▤"),
        "cases": ("판례 검색", "case_query", "⚖"),
    }[kind]
    placeholder = "예: 보증금 반환, 퇴직금, 할부항변권"
    st.markdown(f"### {icon} {title}")
    source = "Backend API 자료" if get_frontend_settings().frontend_data_mode.lower() == "api" else "화면용 예시 자료"
    st.caption(f"현재 선택한 법률 분야 안에서 {source}를 검색합니다.")
    with st.form(f"{kind}-search-form"):
        query = st.text_input("검색어", key=key, placeholder=placeholder, max_chars=200)
        submitted = st.form_submit_button("검색하기", type="primary", use_container_width=True)
    if not submitted:
        return None
    if not 2 <= len(query.strip()) <= 200:
        st.warning("검색어를 2~200자로 입력해 주세요.")
        return ""
    return query.strip()
