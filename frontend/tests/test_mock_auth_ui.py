from pathlib import Path

from streamlit.testing.v1 import AppTest


APP = Path(__file__).parents[1] / "app.py"


def test_member_login_and_logout_flow() -> None:
    app = AppTest.from_file(str(APP)).run(timeout=20)
    app.text_input(key="mock-login-email").set_value("user@lawpath.demo")
    app.text_input(key="mock-login-password").set_value("Demo1234!")
    next(button for button in app.button if button.label == "로그인").click()
    app = app.run(timeout=20)

    assert not app.exception
    assert app.session_state["current_user"]["role"] == "USER"
    assert app.session_state["current_user"]["email"] == "user@lawpath.demo"
    assert not any("password" in key for key in app.session_state["current_user"])
    assert "mock-login-password" not in app.session_state

    app.button(key="mock-logout").click()
    app = app.run(timeout=20)
    assert app.session_state["current_user"]["role"] == "GUEST"


def test_signup_logs_in_new_mock_member() -> None:
    app = AppTest.from_file(str(APP)).run(timeout=20)
    app.text_input(key="mock-signup-email").set_value("new@lawpath.demo")
    app.text_input(key="mock-signup-name").set_value("새회원")
    app.text_input(key="mock-signup-password").set_value("NewUser123!")
    app.text_input(key="mock-signup-confirm").set_value("NewUser123!")
    app.checkbox(key="mock-signup-terms").check()
    app.checkbox(key="mock-signup-privacy").check()
    next(button for button in app.button if button.label == "DEMO 회원가입").click()
    app = app.run(timeout=20)

    assert not app.exception
    assert app.session_state["current_user"]["role"] == "USER"
    assert app.session_state["current_user"]["display_name"] == "새회원"
    assert any(account["email"] == "new@lawpath.demo" for account in app.session_state["mock_accounts"])
    assert "mock-signup-password" not in app.session_state
    assert "mock-signup-confirm" not in app.session_state


def test_admin_login_exposes_admin_menu_and_guest_cannot_see_it() -> None:
    app = AppTest.from_file(str(APP)).run(timeout=20)
    assert "nav-admin-faq" not in [button.key for button in app.sidebar.button]

    app.text_input(key="mock-login-email").set_value("admin@lawpath.demo")
    app.text_input(key="mock-login-password").set_value("Admin1234!")
    next(button for button in app.button if button.label == "로그인").click()
    app = app.run(timeout=20)
    app.button(key="category-housing").click()
    app = app.run(timeout=20)

    assert app.session_state["current_user"]["role"] == "ADMIN"
    assert app.sidebar.button(key="nav-admin-faq")


def test_invalid_login_keeps_guest_role() -> None:
    app = AppTest.from_file(str(APP)).run(timeout=20)
    app.text_input(key="mock-login-email").set_value("user@lawpath.demo")
    app.text_input(key="mock-login-password").set_value("Wrong1234!")
    next(button for button in app.button if button.label == "로그인").click()
    app = app.run(timeout=20)

    assert app.session_state["current_user"]["role"] == "GUEST"
    assert any("올바르지 않습니다" in error.value for error in app.error)
