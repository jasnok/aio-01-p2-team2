import hashlib
import re
from copy import deepcopy
from uuid import uuid4


EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def hash_mock_password(password: str) -> str:
    """DEMO 비교용 해시. 실제 서비스에서는 Backend의 Argon2/bcrypt를 사용한다."""
    return hashlib.sha256(f"lawpath-demo::{password}".encode("utf-8")).hexdigest()


def build_demo_accounts() -> list[dict]:
    return [
        {
            "id": "user-demo",
            "email": "user@lawpath.demo",
            "display_name": "법률초보",
            "role": "USER",
            "password_hash": hash_mock_password("Demo1234!"),
        },
        {
            "id": "admin-demo",
            "email": "admin@lawpath.demo",
            "display_name": "관리자",
            "role": "ADMIN",
            "password_hash": hash_mock_password("Admin1234!"),
        },
    ]


def validate_email(email: str) -> str | None:
    if not EMAIL_PATTERN.fullmatch(email.strip().lower()):
        return "이메일 형식을 확인해 주세요."
    return None


def validate_password(password: str) -> list[str]:
    errors = []
    if len(password) < 8:
        errors.append("8자 이상")
    if not any(character.isalpha() for character in password):
        errors.append("영문 포함")
    if not any(character.isdigit() for character in password):
        errors.append("숫자 포함")
    if not any(not character.isalnum() for character in password):
        errors.append("특수문자 포함")
    return errors


def signup_mock(
    accounts: list[dict],
    *,
    email: str,
    display_name: str,
    password: str,
    password_confirm: str,
    terms_checked: bool,
    privacy_checked: bool,
) -> dict:
    normalized_email = email.strip().lower()
    email_error = validate_email(normalized_email)
    if email_error:
        raise ValueError(email_error)
    if len(display_name.strip()) < 2:
        raise ValueError("닉네임을 2자 이상 입력해 주세요.")
    password_errors = validate_password(password)
    if password_errors:
        raise ValueError(f"비밀번호 조건: {', '.join(password_errors)}")
    if password != password_confirm:
        raise ValueError("비밀번호 확인이 일치하지 않습니다.")
    if not terms_checked or not privacy_checked:
        raise ValueError("필수 약관과 개인정보 처리 안내에 동의해 주세요.")
    if any(account["email"] == normalized_email for account in accounts):
        raise ValueError("이미 사용 중인 이메일입니다.")
    if any(account["display_name"] == display_name.strip() for account in accounts):
        raise ValueError("이미 사용 중인 닉네임입니다.")
    account = {
        "id": f"mock-user-{uuid4()}",
        "email": normalized_email,
        "display_name": display_name.strip(),
        "role": "USER",
        "password_hash": hash_mock_password(password),
    }
    accounts.append(account)
    return public_user(account)


def login_mock(accounts: list[dict], email: str, password: str) -> dict:
    normalized_email = email.strip().lower()
    email_error = validate_email(normalized_email)
    if email_error:
        raise ValueError(email_error)
    account = next((item for item in accounts if item["email"] == normalized_email), None)
    if not account or account["password_hash"] != hash_mock_password(password):
        raise ValueError("이메일 또는 비밀번호가 올바르지 않습니다.")
    return public_user(account)


def request_password_reset_mock(accounts: list[dict], email: str) -> str:
    email_error = validate_email(email)
    if email_error:
        raise ValueError(email_error)
    # 계정 존재 여부를 노출하지 않는 실제 서비스의 응답 방식을 미리 적용한다.
    return "등록 여부와 관계없이 DEMO 재설정 안내를 표시했습니다. 실제 이메일은 발송하지 않습니다."


def public_user(account: dict) -> dict:
    return deepcopy({key: account[key] for key in ("id", "email", "display_name", "role")})
