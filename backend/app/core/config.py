from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    backend_mock_mode: bool = True
    frontend_origin: str = "http://192.100.200.232:8501"
    legal_mcp_url: str = "http://192.100.200.72:8013/mcp"
    mcp_request_timeout_seconds: float = 15
    request_timeout_seconds: float = 15
    max_tool_calls: int = 3
    llm_provider: str = "mock"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5-mini"

    # 통합 실행용 루트 .env를 먼저 읽고, 서비스 전용 파일이 있으면 덮어씁니다.
    model_config = SettingsConfigDict(env_file=(".env", "backend/.env"), extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
