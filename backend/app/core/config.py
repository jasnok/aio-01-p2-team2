from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    mcp_server_url: str = "http://192.100.200.72:8011"
    request_timeout_seconds: float = 15
    max_tool_calls: int = 3
    llm_provider: str = "mock"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

