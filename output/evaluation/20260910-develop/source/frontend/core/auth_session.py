"""Session-scoped identity changes and token expiry; no browser persistence."""
from time import time

import streamlit as st
from pydantic import ValidationError

from frontend.core.storage_models import LoginView, UserView


def clear_private_state():
    for key in list(st.session_state):
        if key.startswith(("terms_", "history_", "history-", "saved_", "api-history", "analysis_save")):
            st.session_state.pop(key, None)
    for key in ("sse_pending", "legal_terms_last", "analysis_terms_chat"):
        st.session_state.pop(key, None)
    st.session_state.update(last_result=None, analysis_error=None, analysis_in_progress=False,
                            session_history=[], conversation_messages=[], notifications=[],
                            question_message="", analysis_draft="", follow_up_input="",
                            unlocked_question_ids=set(), question_edit_id=None)


def apply_login(payload):
    from frontend.clients.backend_client import BackendClientError
    try:
        value = LoginView.model_validate({**payload, "access_token": payload.get("access_token") or payload.get("session_token")})
        if value.user.role == "GUEST":
            raise ValueError("Guest login")
    except (ValidationError, ValueError, TypeError) as error:
        raise BackendClientError("로그인 응답 형식을 확인할 수 없습니다.", "CONTRACT_MISMATCH") from error
    clear_private_state()
    st.session_state.auth_token = value.access_token
    st.session_state.auth_expires_in = value.expires_in
    st.session_state.auth_expires_at = time() + value.expires_in if value.expires_in else None
    st.session_state.current_user = value.user.model_dump()
    st.session_state.mock_role = value.user.role
    st.session_state.auth_checked_at = 0
    st.session_state.auth_invalid = False


def expire_session(message="로그인이 만료되었습니다. 다시 로그인해 주세요."):
    clear_private_state()
    st.session_state.auth_token = None
    st.session_state.auth_expires_at = None
    st.session_state.auth_expires_in = None
    st.session_state.auth_invalid = False
    st.session_state.current_user = dict(id=f"guest-{st.session_state.session_id}", role="GUEST", display_name="비회원")
    st.session_state.mock_role = "GUEST"
    st.session_state.auth_message = message


def refresh_auth():
    from frontend.clients import backend_client as api
    token = st.session_state.auth_token
    if not token:
        return
    if st.session_state.get("auth_invalid") or (st.session_state.get("auth_expires_at") and time() >= st.session_state.auth_expires_at):
        expire_session()
        return
    if time() - st.session_state.get("auth_checked_at", 0) < 60:
        return
    try:
        payload = api.get_current_user(token, "")
        user = UserView.model_validate(payload.get("user", payload))
        if user.role == "GUEST" or payload.get("authenticated") is False:
            expire_session()
        else:
            if str(user.id) != str(st.session_state.current_user["id"]):
                clear_private_state()
            st.session_state.current_user = user.model_dump()
            st.session_state.auth_checked_at = time()
    except api.BackendClientError as error:
        if error.status_code == 401:
            expire_session()
        else:
            st.warning("로그인 상태를 확인하지 못했습니다. 잠시 후 다시 시도해 주세요.")
    except (ValidationError, TypeError):
        expire_session("로그인 정보를 확인할 수 없습니다. 다시 로그인해 주세요.")
