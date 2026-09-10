from __future__ import annotations

from dataclasses import dataclass

import asyncpg

from backend.app.db.pool import get_db_pool


class DuplicateEmailError(ValueError):
    pass


@dataclass(frozen=True)
class DbUser:
    id: int
    email: str
    password_hash: str
    display_name: str
    role: str
    is_active: bool

    def public(self) -> dict:
        return {"id": self.id, "role": self.role, "display_name": self.display_name}


class UserRepository:
    async def create_member(
        self,
        *,
        email: str,
        password_hash: str,
        display_name: str,
    ) -> DbUser:
        pool = await get_db_pool()
        try:
            async with pool.acquire() as connection:
                row = await connection.fetchrow(
                    """
                    INSERT INTO users (email, password_hash, display_name, role, is_active)
                    VALUES ($1, $2, $3, 'USER', TRUE)
                    RETURNING id, email, password_hash, display_name, role, is_active
                    """,
                    email,
                    password_hash,
                    display_name,
                )
        except asyncpg.UniqueViolationError as error:
            raise DuplicateEmailError(email) from error
        return self._to_user(row)

    async def find_by_email(self, email: str) -> DbUser | None:
        pool = await get_db_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                SELECT id, email, password_hash, display_name, role, is_active
                FROM users
                WHERE LOWER(email) = LOWER($1)
                ORDER BY id ASC
                LIMIT 1
                """,
                email,
            )
        return self._to_user(row) if row else None

    async def find_by_id(self, user_id: int) -> DbUser | None:
        pool = await get_db_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                SELECT id, email, password_hash, display_name, role, is_active
                FROM users
                WHERE id = $1
                """,
                user_id,
            )
        return self._to_user(row) if row else None

    @staticmethod
    def _to_user(row: asyncpg.Record) -> DbUser:
        return DbUser(
            id=int(row["id"]),
            email=str(row["email"]),
            password_hash=str(row["password_hash"]),
            display_name=str(row["display_name"]),
            role=str(row["role"]),
            is_active=bool(row["is_active"]),
        )
