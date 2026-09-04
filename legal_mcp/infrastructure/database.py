"""SQLAlchemy engine 생성 위치. 연결 문자열을 로그에 남기지 않습니다."""

from sqlalchemy import Engine, create_engine


def create_database_engine(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True)
