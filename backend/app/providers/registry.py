from backend.app.providers.base import LLMProvider
from backend.app.providers.mock import MockProvider
from backend.app.providers.openai import OpenAIProvider

_PROVIDERS: dict[str, LLMProvider] = {"mock": MockProvider(), "openai": OpenAIProvider()}


def get_provider(name: str) -> LLMProvider:
    try:
        return _PROVIDERS[name]
    except KeyError as error:
        raise ValueError(f"지원하지 않는 Provider입니다: {name}") from error
