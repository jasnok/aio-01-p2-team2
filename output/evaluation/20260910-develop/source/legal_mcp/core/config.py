"""Legal MCP Server 환경 설정."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    """환경변수 기반 MCP 설정."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # MCP Server
    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8011

    # Database
    database_url: str

    # Embedding
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536
    openai_api_key: str

    # Retrieval / Hybrid Search
    retrieval_top_k: int = Field(default=3, ge=1, le=10)
    retrieval_score_threshold: float = Field(default=0.5, ge=0, le=1)
    vector_weight: float = Field(default=0.7, ge=0, le=1)
    keyword_weight: float = Field(default=0.3, ge=0, le=1)

    @model_validator(mode="after")
    def validate_search_weights(self) -> "Settings":
        total = self.vector_weight + self.keyword_weight

        if abs(total - 1.0) > 0.001:
            raise ValueError(
                "VECTOR_WEIGHT와 KEYWORD_WEIGHT의 합은 1이어야 합니다."
            )

        return self


@lru_cache
def get_settings() -> Settings:
    """설정을 한 번만 생성해 재사용한다."""
    return Settings()