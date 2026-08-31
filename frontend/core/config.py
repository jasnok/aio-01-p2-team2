from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class FrontendSettings(BaseSettings):
    backend_api_url: str = "http://127.0.0.1:8000"
    frontend_request_timeout_seconds: float = 30

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def normalized_backend_url(self) -> str:
        return self.backend_api_url.rstrip("/")


@lru_cache
def get_frontend_settings() -> FrontendSettings:
    return FrontendSettings()

