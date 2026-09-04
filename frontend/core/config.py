from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class FrontendSettings(BaseSettings):
    backend_api_url: str = "http://127.0.0.1:8000"
    frontend_request_timeout_seconds: float = 30
    frontend_data_mode: str = "mock"
    frontend_qa_mode: bool = False

    # 통합 실행용 루트 .env를 먼저 읽고, 서비스 전용 파일이 있으면 덮어씁니다.
    model_config = SettingsConfigDict(env_file=(".env", "frontend/.env"), extra="ignore")

    @property
    def normalized_backend_url(self) -> str:
        return self.backend_api_url.rstrip("/")


@lru_cache
def get_frontend_settings() -> FrontendSettings:
    return FrontendSettings()
