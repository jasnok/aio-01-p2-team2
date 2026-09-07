"""이전 import 경로 호환용. 새 코드는 backend.app.providers를 사용합니다."""

from backend.app.providers.registry import get_provider

__all__ = ["get_provider"]
