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
        from frontend.components.notification_center import render_notification_center
        from frontend.services.mock_notification_service import unread_count
        from frontend.core.config import get_frontend_settings

        unread = unread_count(st.session_state.get("notifications", []))
        if get_frontend_settings().frontend_data_mode.lower() == "api":
            from frontend.clients import backend_client

            try:
                unread = backend_client.get_unread_count(st.session_state.auth_token, f"guest-{st.session_state.session_id}")
            except backend_client.BackendClientError:
                unread = 0
        with st.popover(f"🔔 알림 {unread}", use_container_width=True):
            render_notification_center()
    with user_area:
        user = st.session_state.current_user
        role_label = {"GUEST": "비회원", "USER": "회원", "ADMIN": "관리자"}[user["role"]]
        label = "👤 로그인" if user["role"] == "GUEST" else f"👤 {role_label}"
        with st.popover(label, use_container_width=True):
            from frontend.components.mock_auth import render_mock_auth

            render_mock_auth()
            st.divider()
            st.caption(f"현재 세션 · {st.session_state.session_id[-8:]}")
            policy = "7일 보관 예정" if user["role"] == "GUEST" else "영구보관 예정"
            mode = get_frontend_settings().frontend_data_mode.lower()
            location = "Backend API" if mode == "api" else "브라우저 Session"
            st.write(f"질의 이력 조회: {location}. DB 영속 저장과 보관 정책은 연결 확인 전입니다.")
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
