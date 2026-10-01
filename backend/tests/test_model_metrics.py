import asyncio
from types import SimpleNamespace
from backend.app.services.model_metrics import calls, record_call


def test_parallel_requests_do_not_share_model_call_records():
    async def worker(name):
        sink = []
        token = calls.set(sink)
        try:
            await asyncio.sleep(0)
            await asyncio.to_thread(record_call, name, SimpleNamespace(model="test", elapsed_ms=1,
                                                                      usage={"input_tokens": 3}))
            return sink
        finally:
            calls.reset(token)
    async def run():
        return await asyncio.gather(worker("intake"), worker("verification"))
    left, right = asyncio.run(run())
    assert [row["stage"] for row in left] == ["intake"]
    assert [row["stage"] for row in right] == ["verification"]
    assert calls.get() is None
