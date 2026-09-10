from __future__ import annotations

from backend.app.repositories.user_repository import DbUser, UserRepository
from backend.app.services.password_service import hash_password, verify_password


class InvalidCredentialsError(PermissionError):
    pass


class InactiveUserError(PermissionError):
    pass


class AuthService:
    def __init__(self, users: UserRepository | None = None) -> None:
        self.users = users or UserRepository()

    async def register(self, email: str, password: str, display_name: str) -> DbUser:
        return await self.users.create_member(
            email=email.strip().lower(),
            password_hash=hash_password(password),
            display_name=display_name.strip(),
        )

    async def login(self, email: str, password: str) -> DbUser:
        user = await self.users.find_by_email(email.strip().lower())
        if user is None or not verify_password(password, user.password_hash):
            raise InvalidCredentialsError()
        if not user.is_active:
            raise InactiveUserError()
        return user

    async def actor(self, user_id: int) -> dict | None:
        user = await self.users.find_by_id(user_id)
        if user is None or not user.is_active:
            return None
        return user.public()
