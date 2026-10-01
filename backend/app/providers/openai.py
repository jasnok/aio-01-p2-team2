"""Responses adapters share connections and retain a sync CLI boundary."""
import asyncio
from functools import lru_cache
from time import perf_counter
from weakref import WeakKeyDictionary
from typing import Any
from pydantic import BaseModel
from backend.app.core.config import get_settings
from backend.app.providers.models import ProviderResult

_async_clients = WeakKeyDictionary()


@lru_cache(maxsize=4)
def _sync_client(api_key, timeout):
    from openai import OpenAI
    return OpenAI(api_key=api_key, timeout=timeout, max_retries=1)


def _async_client(api_key, timeout):
    from openai import AsyncOpenAI
    clients = _async_clients.setdefault(asyncio.get_running_loop(), {})
    key = (api_key, timeout)
    if key not in clients:
        clients[key] = AsyncOpenAI(api_key=api_key, timeout=timeout, max_retries=1)
    return clients[key]


async def close_async_clients():
    clients = _async_clients.pop(asyncio.get_running_loop(), {})
    for client in clients.values():
        await client.close()


class OpenAIProvider:
    name = "openai"

    def __init__(self, model: str | None = None, *, reasoning_effort: str | None = None):
        self.model_override = model
        self.reasoning_effort = reasoning_effort

    def _connection(self, asynchronous=False):
        settings = get_settings()
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")
        factory = _async_client if asynchronous else _sync_client
        return factory(settings.openai_api_key, settings.request_timeout_seconds)

    def _arguments(self, system_prompt, message, response_schema=None):
        args = {"model": self.model_override or get_settings().openai_model,
                "instructions": system_prompt, "input": message}
        if response_schema is not None:
            args["text_format"] = response_schema
        if self.reasoning_effort:
            args["reasoning"] = {"effort": self.reasoning_effort}
        return args

    def _result(self, response, model, started, structured=True):
        if structured and response.output_parsed is None:
            raise RuntimeError("OpenAI가 구조화된 결과를 반환하지 않았습니다.")
        usage = response.usage
        output = response.output_parsed.model_dump() if structured else response.output_text
        return ProviderResult(self.name, getattr(response, "model", model), output, round((perf_counter()-started)*1000), {
            "input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens,
            "total_tokens": usage.total_tokens} if usage else {})

    def generate(self, system_prompt: str, message: str) -> ProviderResult:
        started = perf_counter()
        args = self._arguments(system_prompt, message)
        return self._result(self._connection().responses.create(**args), args["model"], started, False)

    def generate_structured(self, system_prompt: str, message: str, response_schema: type[BaseModel]) -> ProviderResult:
        started = perf_counter()
        args = self._arguments(system_prompt, message, response_schema)
        return self._result(self._connection().responses.parse(**args), args["model"], started)

    async def generate_structured_async(self, system_prompt: str, message: str, response_schema: type[BaseModel]) -> ProviderResult:
        started = perf_counter()
        args = self._arguments(system_prompt, message, response_schema)
        response = await self._connection(True).responses.parse(**args)
        return self._result(response, args["model"], started)

    def status(self) -> dict[str, Any]:
        settings = get_settings()
        return {"provider": self.name, "configured": bool(settings.openai_api_key),
                "model": self.model_override or settings.openai_model}
