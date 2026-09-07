import streamlit as st

from frontend.data.mock_community import ROLE_USERS
from frontend.services.mock_auth_service import login_mock, request_password_reset_mock, signup_mock
from frontend.services.mock_notification_service import add_notification


def _clear_auth_inputs() -> None:
    for key in (
        "mock-login-password",
        "mock-signup-password",
        "mock-signup-confirm",
    ):
        if key in st.session_state:
            del st.session_state[key]


def _set_authenticated_user(user: dict, message: str) -> None:
    _clear_auth_inputs()
    st.session_state.current_user = user
    st.session_state.mock_role = user["role"]
    st.session_state.auth_message = message
    st.session_state.question_edit_id = None
    st.session_state.unlocked_question_ids = set()
    add_notification(
        st.session_state.notifications,
        "AUTH_SUCCESS",
        message,
        f"{user['display_name']}님, 현재 Mock Session에서 로그인 상태를 확인할 수 있습니다.",
        severity="success",
    )


def _logout() -> None:
    _clear_auth_inputs()
    guest = ROLE_USERS["GUEST"].copy()
    guest["id"] = f"guest-{st.session_state.session_id}"
    st.session_state.current_user = guest
    st.session_state.mock_role = "GUEST"
    st.session_state.auth_message = "로그아웃했습니다."
    st.session_state.question_edit_id = None
    st.session_state.unlocked_question_ids = set()
    st.session_state.selected_feature = "analysis"
    add_notification(
        st.session_state.notifications,
        "LOGOUT",
        "로그아웃되었습니다.",
        "현재 브라우저가 비회원 상태로 전환되었습니다.",
        severity="info",
    )


def render_mock_auth() -> None:
    user = st.session_state.current_user
    st.warning("DEMO 인증입니다. 실제 개인정보나 사용 중인 비밀번호를 입력하지 마세요.")
    if st.session_state.auth_message:
        st.success(st.session_state.auth_message)

    if user["role"] != "GUEST":
        st.markdown(f"### 👤 {user['display_name']}")
        st.caption(f"{user.get('email', 'DEMO 계정')} · {user['role']}")
        st.write("회원 질의 이력은 실제 연동 후 계정에 영속 보관할 예정입니다.")
        st.button("로그아웃", key="mock-logout", on_click=_logout, use_container_width=True)
        return

    login_tab, signup_tab, reset_tab = st.tabs(["로그인", "회원가입", "비밀번호 재설정"])
    with login_tab:
        st.caption("회원: user@lawpath.demo / Demo1234!")
        st.caption("관리자: admin@lawpath.demo / Admin1234!")
        with st.form("mock-login-form"):
            email = st.text_input("이메일", key="mock-login-email")
            password = st.text_input("비밀번호", type="password", key="mock-login-password")
            submitted = st.form_submit_button("로그인", type="primary", use_container_width=True)
        if submitted:
            try:
                user = login_mock(st.session_state.mock_accounts, email, password)
                _set_authenticated_user(user, "DEMO 로그인이 완료되었습니다.")
                st.rerun()
            except ValueError as error:
                st.error(str(error))

    with signup_tab:
        with st.form("mock-signup-form", clear_on_submit=False):
            email = st.text_input("가입 이메일", key="mock-signup-email")
            display_name = st.text_input("닉네임", max_chars=30, key="mock-signup-name")
            password = st.text_input("가입 비밀번호", type="password", key="mock-signup-password", help="8자 이상, 영문·숫자·특수문자를 포함해 주세요.")
            password_confirm = st.text_input("비밀번호 확인", type="password", key="mock-signup-confirm")
            terms = st.checkbox("서비스 이용약관에 동의합니다. (필수)", key="mock-signup-terms")
            privacy = st.checkbox("개인정보 처리 안내에 동의합니다. (필수)", key="mock-signup-privacy")
            submitted = st.form_submit_button("DEMO 회원가입", type="primary", use_container_width=True)
        if submitted:
            try:
                user = signup_mock(
                    st.session_state.mock_accounts,
                    email=email,
                    display_name=display_name,
                    password=password,
                    password_confirm=password_confirm,
                    terms_checked=terms,
                    privacy_checked=privacy,
                )
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
