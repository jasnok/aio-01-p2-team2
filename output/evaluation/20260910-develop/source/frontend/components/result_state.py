import streamlit as st


def render_empty(message: str) -> None:
    st.markdown(f'<div class="empty-state">{message}</div>', unsafe_allow_html=True)


def render_demo_banner() -> None:
    st.markdown('<div class="demo-banner">⚠ DEMO MODE — 화면과 검색 동작 확인용 예시 데이터입니다. 실제 법률정보로 사용하지 마세요.</div>', unsafe_allow_html=True)
