import asyncio

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.repositories.user_repository import DbUser
from backend.app.routers import mock_api
from backend.app.services.auth_service import AuthService, InactiveUserError, InvalidCredentialsError
from backend.app.services.password_service import hash_password


client = TestClient(app)


class FakeUsers:
    def __init__(self) -> None:
        self.user = DbUser(
            id=42,
            email="member@example.com",
            password_hash=hash_password("Password123!"),
            display_name="회원",
            role="USER",
            is_active=True,
        )

    async def create_member(self, **_kwargs):
        return self.user

    async def find_by_email(self, _email):
        return self.user

    async def find_by_id(self, user_id):
        return self.user if user_id == 42 else None


def real_settings():
    return type("Settings", (), {"backend_mock_mode": False})()


def mock_settings():
    return type("Settings", (), {"backend_mock_mode": True})()


def test_auth_service_verifies_hash_and_active_member() -> None:
    service = AuthService(FakeUsers())
    user = asyncio.run(service.login("member@example.com", "Password123!"))
    assert user.id == 42

    with __import__("pytest").raises(InvalidCredentialsError):
        asyncio.run(service.login("member@example.com", "wrong-password"))


def test_db_register_and_login_issue_opaque_session(monkeypatch) -> None:
    service = AuthService(FakeUsers())

    async def issue(user_id):
        assert user_id == 42
        return "db-session-token", 28800

    monkeypatch.setattr(mock_api, "get_settings", real_settings)
    monkeypatch.setattr(mock_api, "auth_service", service)
    monkeypatch.setattr(mock_api.sessions, "issue", issue)

    registered = client.post(
        "/api/auth/register",
        json={"email": "member@example.com", "password": "Password123!", "display_name": "회원"},
    )
    assert registered.status_code == 201
    assert registered.json()["session_token"] == "db-session-token"
    assert registered.json()["user"]["id"] == 42

    logged_in = client.post(
        "/api/auth/login",
        json={"email": "member@example.com", "password": "Password123!"},
    )
    assert logged_in.status_code == 200
    assert logged_in.json()["user"]["role"] == "USER"


def test_db_session_resolves_actor_from_users_table(monkeypatch) -> None:
    service = AuthService(FakeUsers())

    async def read(token):
        assert token == "db-session-token"
        return type("Session", (), {"user_id": 42})()

    monkeypatch.setattr(mock_api, "get_settings", real_settings)
    monkeypatch.setattr(mock_api, "auth_service", service)
    monkeypatch.setattr(mock_api.sessions, "read", read)

    response = client.get("/api/auth/me", headers={"Authorization": "Bearer db-session-token"})
    assert response.status_code == 200
    assert response.json()["authenticated"] is True
    assert response.json()["user"]["id"] == 42


def test_mock_demo_login_remains_available_when_mock_mode_enabled(monkeypatch) -> None:
    monkeypatch.setattr(mock_api, "get_settings", mock_settings)
    response = client.post(
        "/api/auth/login",
        json={"email": "user@lawpath.demo", "password": "Demo1234!"},
    )
    assert response.status_code == 200
    assert response.json()["user"]["role"] == "USER"
