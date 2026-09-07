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
        with st.popover("❓ 도움말", use_container_width=True):
            st.markdown("### ❓ LawPath 도움말")
            st.write("홈에서 법률 분야를 선택한 뒤 원하는 기능을 이용하세요.")
            st.markdown("**빠른 이용 순서**")
            st.markdown("1. 분야 선택\n2. 사례 입력\n3. 관련 법령·사례 확인")
            st.warning("현재는 화면 확인용 DEMO 데이터입니다.")
    with notice_area:
        notices = st.session_state.get("notifications", [])
        with st.popover(f"🔔 알림 {len(notices)}", use_container_width=True):
            st.markdown("### 🔔 알림")
            if notices:
                for notice in notices:
                    st.info(notice)
            else:
                st.caption("새로운 알림이 없습니다.")
    with user_area:
        user = st.session_state.current_user
        role_label = {"GUEST": "비회원", "USER": "회원", "ADMIN": "관리자"}[user["role"]]
        with st.popover(f"👤 {role_label}", use_container_width=True):
            st.markdown(f"### 👤 {user['display_name']}")
            st.caption("Mock 역할 · 실제 인증 아님")
            st.caption(f"현재 세션 · {st.session_state.session_id[-8:]}")
            policy = "7일 보관 예정" if user["role"] == "GUEST" else "영구보관 예정"
            st.write(f"질의 이력 정책: {policy}. 현재는 브라우저 Session에만 보관됩니다.")
            if st.button("🔄 세션 초기화", key="reset-session", use_container_width=True):
                from frontend.core.session import reset_session

                reset_session()
                st.rerun()
    with action:
        if show_home and st.button("⌂ 홈으로", use_container_width=True):
            from frontend.core.session import go_home

            go_home()
            st.rerun()
    st.divider()
