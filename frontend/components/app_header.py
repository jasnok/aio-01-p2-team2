from pathlib import Path

import streamlit as st


def load_theme() -> None:
    css = (Path(__file__).parents[1] / "styles" / "theme.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def render_header(show_home: bool = False) -> None:
    brand, help_area, notice_area, user_area, action = st.columns([6, 1, 1, 1.2, 1.1])
    with brand:
        st.markdown('<div class="lawpath-brand">⚖ LawPath</div><div class="lawpath-tagline">내 사례와 법을 연결해 드립니다</div>', unsafe_allow_html=True)
    with help_area:
        with st.popover("? 도움말", use_container_width=True):
            st.markdown("**LawPath 사용법**")
            st.write("홈에서 분야를 선택한 뒤 사례 분석, 법 검색 또는 실제 사례 검색을 이용하세요.")
            st.warning("현재는 화면 확인용 DEMO 데이터입니다.")
    with notice_area:
        notices = st.session_state.get("notifications", [])
        with st.popover(f"♢ 알림 {len(notices)}", use_container_width=True):
            for notice in notices:
                st.write(f"• {notice}")
    with user_area:
        with st.popover("○ 비로그인", use_container_width=True):
            st.caption(f"세션: {st.session_state.session_id[-8:]}")
            st.write("질의 이력과 체크 상태는 현재 세션에만 보관됩니다.")
            if st.button("세션 초기화", key="reset-session", use_container_width=True):
                from frontend.core.session import reset_session

                reset_session()
                st.rerun()
    with action:
        if show_home and st.button("⌂ 홈으로", use_container_width=True):
            from frontend.core.session import go_home

            go_home()
            st.rerun()
    st.divider()
