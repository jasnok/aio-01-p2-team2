import pytest
from streamlit.testing.v1 import AppTest

from frontend.clients import backend_client as api


USER = {"id": 42, "role": "USER", "display_name": "회원"}


def refresh_app():
    return AppTest.from_string('''
import streamlit as st
from frontend.core.session import initialize_session
from frontend.core.auth_session import refresh_auth
initialize_session()
def seed():
    st.session_state.update(auth_token="member", current_user=dict(id=42, role="USER", display_name="회원"),
        auth_checked_at=0, last_result=dict(secret="private"), terms_messages=[dict(content="private")])
st.button("seed", on_click=seed)
if st.button("refresh"):
    refresh_auth()
''').run()


@pytest.mark.parametrize("payload", [{"user": USER}, {"user": USER, "authenticated": "true"},
                                    {"user": USER, "authenticated": 1}, {"user": USER, "authenticated": None},
                                    {"user": USER, "authenticated": False},
                                    {"user": {**USER, "role": "GUEST"}, "authenticated": True}])
def test_invalid_or_unauthenticated_refresh_expires_private_state(monkeypatch, payload):
    monkeypatch.setattr(api, "get_current_user", lambda *args: payload)
    app = refresh_app()
    app.button[0].click().run()
    app.button[1].click().run()
    assert not app.exception
    assert app.session_state["auth_token"] is None
    assert app.session_state["last_result"] is None
    assert "terms_messages" not in app.session_state


@pytest.mark.parametrize("role", ["USER", "ADMIN"])
def test_refresh_preserves_same_identity_and_clears_role_change(monkeypatch, role):
    monkeypatch.setattr(api, "get_current_user", lambda *args: {"user": {**USER, "role": role}, "authenticated": True})
    app = refresh_app()
    app.button[0].click().run()
    app.button[1].click().run()
    assert not app.exception
    assert app.session_state["auth_token"] == "member"
    assert app.session_state["current_user"]["role"] == role
    assert app.session_state["auth_checked_at"] > 0
    assert (app.session_state["last_result"] is None) == (role == "ADMIN")


@pytest.mark.parametrize("status", [401, 503])
def test_auth_transport_failure_distinguishes_expiry_from_unavailability(monkeypatch, status):
    def unavailable(*args):
        raise api.BackendClientError("unavailable", status_code=status)
    monkeypatch.setattr(api, "get_current_user", unavailable)
    app = refresh_app()
    app.button[0].click().run()
    app.button[1].click().run()
    assert not app.exception
    assert (app.session_state["auth_token"] is None) == (status == 401)
    assert (app.session_state["last_result"] is None) == (status == 401)
    if status == 503:
        assert app.warning and app.session_state["auth_checked_at"] == 0


@pytest.mark.parametrize("payload", [None, [], "invalid", 42])
def test_nonobject_login_is_a_contract_error(payload):
    from frontend.core.auth_session import apply_login
    with pytest.raises(api.BackendClientError) as caught:
        apply_login(payload)
    assert caught.value.code == "CONTRACT_MISMATCH"
