import pytest

from frontend.services.mock_auth_service import (
    build_demo_accounts,
    login_mock,
    request_password_reset_mock,
    signup_mock,
    validate_password,
)


def test_demo_member_and_admin_can_login_without_exposing_password() -> None:
    accounts = build_demo_accounts()
    member = login_mock(accounts, "user@lawpath.demo", "Demo1234!")
    admin = login_mock(accounts, "admin@lawpath.demo", "Admin1234!")

    assert member["role"] == "USER"
    assert admin["role"] == "ADMIN"
    assert "password_hash" not in member
    assert all("password" not in account for account in accounts)


def test_login_rejects_wrong_credentials() -> None:
    with pytest.raises(ValueError, match="올바르지 않습니다"):
        login_mock(build_demo_accounts(), "user@lawpath.demo", "Wrong1234!")


@pytest.mark.parametrize(
    "password,expected",
    [
        ("short", ["8자 이상", "숫자 포함", "특수문자 포함"]),
        ("onlyletters", ["숫자 포함", "특수문자 포함"]),
        ("Letters123", ["특수문자 포함"]),
    ],
)
def test_password_validation(password: str, expected: list[str]) -> None:
    assert validate_password(password) == expected


def test_signup_validates_and_stores_only_mock_hash() -> None:
    accounts = build_demo_accounts()
    user = signup_mock(
        accounts,
        email="new@lawpath.demo",
        display_name="새회원",
        password="NewUser123!",
        password_confirm="NewUser123!",
        terms_checked=True,
        privacy_checked=True,
    )

    assert user["role"] == "USER"
    assert user["email"] == "new@lawpath.demo"
    stored = next(account for account in accounts if account["email"] == user["email"])
    assert stored["password_hash"] != "NewUser123!"
    assert "password" not in stored


@pytest.mark.parametrize(
    "changes,message",
    [
        ({"email": "잘못된주소"}, "이메일 형식"),
        ({"display_name": "한"}, "닉네임"),
        ({"password_confirm": "Different123!"}, "일치하지"),
        ({"terms_checked": False}, "동의"),
    ],
)
def test_signup_rejects_invalid_input(changes: dict, message: str) -> None:
    values = {
        "email": "new@lawpath.demo",
        "display_name": "새회원",
        "password": "NewUser123!",
        "password_confirm": "NewUser123!",
        "terms_checked": True,
        "privacy_checked": True,
    }
    values.update(changes)
    with pytest.raises(ValueError, match=message):
        signup_mock(build_demo_accounts(), **values)


def test_password_reset_response_does_not_reveal_account_existence() -> None:
    accounts = build_demo_accounts()
    known = request_password_reset_mock(accounts, "user@lawpath.demo")
    unknown = request_password_reset_mock(accounts, "unknown@lawpath.demo")
    assert known == unknown
