import asyncio
from types import SimpleNamespace
import pytest
from backend.app.services.model_metrics import collect_calls, structured_call
from backend.app.providers import openai as adapter


def test_async_timeout_cancels_only_the_timed_out_call_and_records_unknown_usage():
    class Provider:
        cancelled = False
        async def generate_structured_async(self, prompt, message, schema):
            if message == "slow":
                try:
                    await asyncio.sleep(10)
                finally:
                    self.cancelled = True
            return SimpleNamespace(model="fake", elapsed_ms=1, usage={"input_tokens": 1})
    async def run():
        provider = Provider()
        with collect_calls() as records:
            slow = structured_call(provider, "answer", "", "slow", None, .01)
            fast = structured_call(provider, "intake", "", "fast", None, 1)
            values = await asyncio.gather(slow, fast, return_exceptions=True)
            assert isinstance(values[0], TimeoutError)
            assert values[1].model == "fake" and provider.cancelled
        assert len(records) == 2
        failed = next(row for row in records if row["status"] == "failed")
        assert failed["usage_known"] is False and failed["usage"] == {}
    asyncio.run(run())


def test_clients_are_shared_by_loop_and_closed_on_shutdown(monkeypatch):
    import openai
    created = []
    class Client:
        closed = False
        def __init__(self, **kwargs):
            created.append(self)
        async def close(self):
            self.closed = True
    monkeypatch.setattr(openai, "AsyncOpenAI", Client)
    async def run():
        first = adapter._async_client("synthetic-key", 10)
        assert adapter._async_client("synthetic-key", 10) is first
        assert adapter._async_client("synthetic-key", 20) is not first
        await adapter.close_async_clients()
        assert all(client.closed for client in created)
    asyncio.run(run())
    assert len(created) == 2


def test_async_provider_passes_model_effort_schema_and_usage(monkeypatch):
    from backend.app.agents.models import AnswerReview
    from backend.app.providers.openai import OpenAIProvider
    async def parse(**args):
        assert args["model"] == "candidate" and args["reasoning"] == {"effort": "low"}
        assert args["text_format"] is AnswerReview
        return SimpleNamespace(output_parsed=AnswerReview(claims=[{
            "claim_index": 0, "verdict": "supported", "reason": "확인"}]),
            usage=SimpleNamespace(input_tokens=10, output_tokens=5, total_tokens=15))
    provider = OpenAIProvider("candidate", reasoning_effort="low")
    monkeypatch.setattr(provider, "_connection", lambda *args: SimpleNamespace(responses=SimpleNamespace(parse=parse)))
    result = asyncio.run(provider.generate_structured_async("prompt", "message", AnswerReview))
    assert result.model == "candidate" and result.usage["total_tokens"] == 15
