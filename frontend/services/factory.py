from functools import lru_cache

from frontend.core.config import get_frontend_settings
from frontend.services.base import LegalService
from frontend.services.mock_legal_service import MockLegalService


@lru_cache
def get_legal_service() -> LegalService:
    mode = get_frontend_settings().frontend_data_mode.lower()
    if mode == "mock":
        return MockLegalService()
    raise ValueError("현재 Frontend 단독 버전은 FRONTEND_DATA_MODE=mock만 지원합니다.")
