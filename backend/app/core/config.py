from functools import lru_cache

from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    backend_mock_mode: bool = True
    frontend_origin: str = "http://127.0.0.1:8501"
    legal_mcp_url: str = "http://127.0.0.1:8013/mcp"
    mcp_request_timeout_seconds: float = 15
    request_timeout_seconds: float = 15
    input_assessment_timeout_seconds: float = 8
    max_tool_calls: int = 3
    llm_provider: str = "mock"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5-mini"
    database_url: str = "postgresql://legal_user:legal_password@127.0.0.1:5434/legal_ai"
    redis_enabled: bool = False
    redis_url: str = "redis://127.0.0.1:6380/0"
    auth_session_ttl_seconds: int = 28800
    guest_session_ttl_seconds: int = 3600
    term_run_ttl_seconds: int = 3600
    agent_run_ttl_seconds: int = 86400
    agent_run_timeout_seconds: int = 150
    citation_mode: Literal["spans", "quotes"] = "spans"
    intake_model: str | None = None
    answer_model: str | None = None
    verification_model: str | None = None
    semantic_verification_enabled: bool = True
    answer_repair_attempts: int = Field(default=1, ge=0, le=1)
    intake_reasoning_effort: Literal["minimal", "low", "medium", "high"] | None = None
    answer_reasoning_effort: Literal["minimal", "low", "medium", "high"] | None = None
    verification_reasoning_effort: Literal["minimal", "low", "medium", "high"] | None = None
    context_max_documents: int = Field(default=6, ge=1, le=6)
    context_max_windows: int = Field(default=3, ge=1, le=3)
    context_document_budget: int = Field(default=2400, ge=300, le=2400)
    compact_verification_context: bool = False
    # 통합 실행용 루트 .env를 먼저 읽고, 서비스 전용 파일이 있으면 덮어씁니다.
    model_config = SettingsConfigDict(env_file=(".env", "backend/.env"), extra="ignore", env_ignore_empty=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
