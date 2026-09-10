from typing import Protocol

from pydantic import BaseModel

from backend.app.providers.models import ProviderResult


class LLMProvider(Protocol):
    name: str

    def generate(self, system_prompt: str, message: str) -> ProviderResult: ...

    def generate_structured(self, system_prompt: str, message: str, response_schema: type[BaseModel]) -> ProviderResult: ...

    def status(self) -> dict: ...
