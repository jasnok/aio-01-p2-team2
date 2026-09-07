import streamlit as st


def render_search_form(kind: str) -> str | None:
    is_law = kind == "laws"
    title = "법 검색" if is_law else "실제 사례 검색"
    key = "law_query" if is_law else "case_query"
    placeholder = "예: 보증금 반환, 퇴직금" if is_law else "예: 계약 종료 후 보증금 미반환"
    st.markdown(f"### {'⌕' if is_law else '⚖'} {title}")
    st.caption("현재 선택한 법률 분야 안에서 화면용 예시 자료를 검색합니다.")
    with st.form(f"{kind}-search-form"):
        query = st.text_input("검색어", key=key, placeholder=placeholder)
        submitted = st.form_submit_button("검색하기", type="primary", use_container_width=True)
    if not submitted:
        return None
    if len(query.strip()) < 2:
        st.warning("검색어를 2자 이상 입력해 주세요.")
        return ""
    return query.strip()
