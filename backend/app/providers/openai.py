"""OpenAI Responses API 어댑터. API Key가 없으면 호출 전에 명확히 실패합니다."""

from time import perf_counter
from typing import Any

from pydantic import BaseModel

from backend.app.core.config import get_settings
from backend.app.providers.models import ProviderResult


class OpenAIProvider:
    name = "openai"

    def __init__(self, model: str | None = None):
        self.model_override = model

    def _client(self):
        settings = get_settings()
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")
        from openai import OpenAI

        return OpenAI(api_key=settings.openai_api_key, timeout=settings.request_timeout_seconds, max_retries=1)

    def generate(self, system_prompt: str, message: str) -> ProviderResult:
        settings = get_settings()
        started = perf_counter()
        response = self._client().responses.create(model=settings.openai_model, instructions=system_prompt, input=message)
        return ProviderResult(self.name, settings.openai_model, response.output_text, round((perf_counter() - started) * 1000))

    def generate_structured(self, system_prompt: str, message: str, response_schema: type[BaseModel]) -> ProviderResult:
        settings = get_settings()
        started = perf_counter()
        model = self.model_override or settings.openai_model
        response = self._client().responses.parse(model=model, instructions=system_prompt, input=message, text_format=response_schema)
        if response.output_parsed is None:
            raise RuntimeError("OpenAI가 구조화된 결과를 반환하지 않았습니다.")
        usage = response.usage
        return ProviderResult(self.name, model, response.output_parsed.model_dump(), round((perf_counter() - started) * 1000), {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "total_tokens": usage.total_tokens,
        } if usage else {})

    def status(self) -> dict[str, Any]:
        settings = get_settings()
        return {"provider": self.name, "configured": bool(settings.openai_api_key), "model": settings.openai_model}
