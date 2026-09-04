from pydantic import BaseModel

from backend.app.providers.models import ProviderResult


class MockProvider:
    name = "mock"

    def generate(self, system_prompt: str, message: str) -> ProviderResult:
        return ProviderResult(self.name, "mock", "Mock Provider 응답", 0)

    def generate_structured(self, system_prompt: str, message: str, response_schema: type[BaseModel]) -> ProviderResult:
        raise NotImplementedError("테스트별 결정적 구조화 Mock을 주입하세요.")

    def status(self) -> dict:
        return {"provider": self.name, "configured": True, "model": "mock"}
