"""PostgreSQL + pgvector 연결을 제공한다."""

import os
from contextlib import contextmanager
from collections.abc import Iterator

import psycopg
from dotenv import load_dotenv
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL 환경변수가 설정되지 않았습니다.")


@contextmanager
def get_connection() -> Iterator[psycopg.Connection]:
    """dict 형태의 행과 pgvector를 지원하는 DB 연결을 제공한다."""
    with psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row,
    ) as connection:
        register_vector(connection)
        yield connection