import asyncpg

from backend.app.core.config import get_settings


_pool: asyncpg.Pool | None = None


async def get_db_pool() -> asyncpg.Pool:
    global _pool

    if _pool is None:
        settings = get_settings()

        _pool = await asyncpg.create_pool(
            dsn=settings.database_url,
            min_size=1,
            max_size=5,
            command_timeout=10,
        )

    return _pool


async def close_db_pool() -> None:
    global _pool

    if _pool is not None:
        await _pool.close()
        _pool = None