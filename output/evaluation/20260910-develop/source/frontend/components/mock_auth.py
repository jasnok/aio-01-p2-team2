import streamlit as st

from frontend.clients import backend_client
from frontend.core.config import get_frontend_settings
from frontend.data.mock_community import ROLE_USERS
from frontend.services.mock_auth_service import login_mock, request_password_reset_mock, signup_mock
from frontend.services.mock_notification_service import add_notification


def _clear_auth_inputs() -> None:
    for key in ("mock-login-password", "mock-signup-password", "mock-signup-confirm", "api-login-password", "api-signup-password", "api-signup-confirm"):
        st.session_state.pop(key, None)


def _set_authenticated_user(user: dict, message: str) -> None:
    _clear_auth_inputs()
    st.session_state.current_user = user
    st.session_state.mock_role = user["role"]
    st.session_state.auth_message = message
    st.session_state.question_edit_id = None
    st.session_state.unlocked_question_ids = set()
    add_notification(st.session_state.notifications, "AUTH_SUCCESS", message, f"{user['display_name']}님, 현재 Mock Session에서 로그인 상태를 확인할 수 있습니다.", severity="success")


def _guest_user() -> dict:
    guest = ROLE_USERS["GUEST"].copy()
    guest["id"] = f"guest-{st.session_state.session_id}"
    return guest


def _logout_mock() -> None:
    _clear_auth_inputs()
    st.session_state.current_user = _guest_user()
    st.session_state.mock_role = "GUEST"
    st.session_state.auth_message = "로그아웃했습니다."
    st.session_state.question_edit_id = None
    st.session_state.unlocked_question_ids = set()
    st.session_state.selected_feature = "analysis"
    add_notification(st.session_state.notifications, "LOGOUT", "로그아웃되었습니다.", "현재 브라우저가 비회원 상태로 전환되었습니다.", severity="info")


def _apply_api_session(payload: dict, message: str) -> None:
    _clear_auth_inputs()
    from frontend.core.auth_session import apply_login
    apply_login(payload)
    st.session_state.auth_message = message
    st.session_state.unlocked_question_ids = set()


def _logout_api() -> None:
    try:
        if st.session_state.auth_token:
            backend_client.logout(st.session_state.auth_token)
    except backend_client.BackendClientError as error:
        st.session_state.auth_message = error.user_message
    from frontend.core.auth_session import expire_session
    expire_session("로그아웃했습니다.")
    st.session_state.selected_feature = "analysis"


def render_mock_auth() -> None:
    if get_frontend_settings().frontend_data_mode.lower() == "api":
        _render_api_auth()
    else:
        _render_local_auth()


def _render_demo_login_accounts() -> None:
    """로그인 테스트용 계정을 값별로 복사할 수 있게 안내한다."""
    with st.expander("📋 테스트 로그인 계정 (클릭해서 복사)", expanded=True):
        st.markdown("**일반 회원**")
        st.caption("이메일")
        st.code("user@lawpath.demo", language=None)
        st.caption("비밀번호")
        st.code("Demo1234!", language=None)

        st.markdown("**관리자**")
        st.caption("이메일")
        st.code("admin@lawpath.demo", language=None)
        st.caption("비밀번호")
        st.code("Admin1234!", language=None)
        st.caption("각 코드 상자 오른쪽의 복사 아이콘을 누른 뒤 로그인 입력란에 붙여 넣으세요.")


def _render_local_auth() -> None:
    user = st.session_state.current_user
    st.warning("DEMO 인증입니다. 실제 개인정보나 사용 중인 비밀번호를 입력하지 마세요.")
    if st.session_state.auth_message:
        st.success(st.session_state.auth_message)
    if user["role"] != "GUEST":
        st.markdown(f"### 👤 {user['display_name']}")
        st.caption(f"{user.get('email', 'DEMO 계정')} · {user['role']}")
        st.write("회원 질의 이력은 실제 연동 후 계정에 영속 보관할 예정입니다.")
        st.button("로그아웃", key="mock-logout", on_click=_logout_mock, use_container_width=True)
        return

    login_tab, signup_tab, reset_tab = st.tabs(["로그인", "회원가입", "비밀번호 재설정"])
    with login_tab:
        _render_demo_login_accounts()
        with st.form("mock-login-form"):
            email = st.text_input("이메일", key="mock-login-email")
            password = st.text_input("비밀번호", type="password", key="mock-login-password")
            submitted = st.form_submit_button("로그인", type="primary", use_container_width=True)
        if submitted:
            try:
                _set_authenticated_user(login_mock(st.session_state.mock_accounts, email, password), "DEMO 로그인이 완료되었습니다.")
                st.rerun()
            except ValueError as error:
                st.error(str(error))
    with signup_tab:
        with st.form("mock-signup-form"):
            email = st.text_input("가입 이메일", key="mock-signup-email")
            display_name = st.text_input("닉네임", max_chars=30, key="mock-signup-name")
            password = st.text_input("가입 비밀번호", type="password", key="mock-signup-password")
            password_confirm = st.text_input("비밀번호 확인", type="password", key="mock-signup-confirm")
            terms = st.checkbox("서비스 이용약관에 동의합니다. (필수)", key="mock-signup-terms")
            privacy = st.checkbox("개인정보 처리 안내에 동의합니다. (필수)", key="mock-signup-privacy")
            submitted = st.form_submit_button("DEMO 회원가입", type="primary", use_container_width=True)
        if submitted:
            try:
                user = signup_mock(st.session_state.mock_accounts, email=email, display_name=display_name, password=password, password_confirm=password_confirm, terms_checked=terms, privacy_checked=privacy)
                _set_authenticated_user(user, "DEMO 회원가입과 로그인이 완료되었습니다.")
                st.rerun()
            except ValueError as error:
                st.error(str(error))
    with reset_tab:
        st.caption("실제 이메일은 발송하지 않습니다.")
        with st.form("mock-password-reset-form"):
            email = st.text_input("재설정 이메일", key="mock-reset-email")
            submitted = st.form_submit_button("재설정 안내 확인", use_container_width=True)
        if submitted:
            try:
                st.info(request_password_reset_mock(st.session_state.mock_accounts, email))
            except ValueError as error:
                st.error(str(error))


def _render_api_auth() -> None:
    user = st.session_state.current_user
    st.info("Backend API 인증 모드입니다. Token은 현재 Streamlit Session에만 보관됩니다.")
    if st.session_state.auth_message:
        st.success(st.session_state.auth_message)
    if user["role"] != "GUEST":
        st.markdown(f"### 👤 {user['display_name']}")
        st.caption(f"{user.get('email', '로그인 계정')} · {user['role']}")
        if st.button("로그아웃", key="api-logout", use_container_width=True):
            _logout_api()
            st.rerun()
        return

    login_tab, signup_tab, reset_tab = st.tabs(["로그인", "회원가입", "비밀번호 재설정"])
    with login_tab:
        _render_demo_login_accounts()
        with st.form("api-login-form"):
            email = st.text_input("이메일", key="api-login-email")
            password = st.text_input("비밀번호", type="password", key="api-login-password")
            submitted = st.form_submit_button("로그인", type="primary", use_container_width=True)
        if submitted:
            try:
                _apply_api_session(backend_client.login(email, password), "로그인이 완료되었습니다.")
                st.rerun()
            except backend_client.BackendClientError as error:
                st.error(error.user_message)
    with signup_tab:
        with st.form("api-signup-form"):
            email = st.text_input("가입 이메일", key="api-signup-email")
            display_name = st.text_input("닉네임", max_chars=30, key="api-signup-name")
            password = st.text_input("가입 비밀번호", type="password", key="api-signup-password")
            password_confirm = st.text_input("비밀번호 확인", type="password", key="api-signup-confirm")
            terms = st.checkbox("서비스 이용약관에 동의합니다. (필수)", key="api-signup-terms")
            privacy = st.checkbox("개인정보 처리 안내에 동의합니다. (필수)", key="api-signup-privacy")
            submitted = st.form_submit_button("회원가입", type="primary", use_container_width=True)
        if submitted:
            if password != password_confirm:
                st.error("비밀번호 확인이 일치하지 않습니다.")
            elif not terms or not privacy:
                st.error("필수 약관과 개인정보 처리 안내에 동의해 주세요.")
            else:
                try:
                    _apply_api_session(backend_client.register(email, password, display_name), "회원가입과 로그인이 완료되었습니다.")
                    st.rerun()
                except backend_client.BackendClientError as error:
                    st.error(error.user_message)
    with reset_tab:
        with st.form("api-password-reset-form"):
            email = st.text_input("재설정 이메일", key="api-reset-email")
            submitted = st.form_submit_button("재설정 안내 요청", use_container_width=True)
        if submitted:
            try:
                payload = backend_client.request_password_reset(email)
                st.info(payload.get("message", "등록 여부와 관계없이 재설정 안내 요청을 처리했습니다."))
            except backend_client.BackendClientError as error:
                st.error(error.user_message)
