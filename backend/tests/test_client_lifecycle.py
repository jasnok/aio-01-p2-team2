import asyncio
import os
from types import SimpleNamespace

import pytest

from backend.app import main
from backend.app.providers import openai as adapter
from backend.app.services import session_service


@pytest.mark.parametrize("failure", [RuntimeError("synthetic close failure"), asyncio.CancelledError()])
def test_model_shutdown_attempts_every_client_even_when_one_fails(failure):
    closed = []
    class Client:
        def __init__(self, name, error=None):
            self.name, self.error = name, error
        async def close(self):
            await asyncio.sleep(0)
            closed.append(self.name)
            if self.error is not None:
                raise self.error
    async def verify():
        loop = asyncio.get_running_loop()
        adapter._async_clients[loop] = {"first": Client("first", failure), "second": Client("second")}
        with pytest.raises(type(failure)):
            await adapter.close_async_clients()
        assert sorted(closed) == ["first", "second"]
        assert loop not in adapter._async_clients
        await adapter.close_async_clients()
    asyncio.run(verify())


def test_redis_close_is_repeatable_resets_reference_and_does_not_create_client(monkeypatch):
    service = session_service.SessionService()
    closed = []
    class Client:
        async def aclose(self):
            closed.append(True)
            raise RuntimeError("synthetic close failure")
    async def verify():
        await service.close()
        service._redis = Client()
        with pytest.raises(RuntimeError):
            await service.close()
        assert service._redis is None
        await service.close()
    monkeypatch.setattr(session_service, "get_settings", lambda: pytest.fail("close must not read config or create a pool"))
    asyncio.run(verify())
    assert closed == [True]


@pytest.mark.parametrize("failing_stage", [None, "runs", "models", "redis"])
def test_lifespan_closes_resources_in_order_and_continues_after_failure(monkeypatch, failing_stage):
    events = []
    def cleanup(stage):
        async def close():
            events.append(stage)
            if stage == failing_stage:
                raise RuntimeError("synthetic close failure")
        return close
    monkeypatch.setattr(main, "close_active_runs", cleanup("runs"))
    monkeypatch.setattr(main, "close_async_clients", cleanup("models"))
    monkeypatch.setattr(main, "sessions", SimpleNamespace(close=cleanup("redis")))
    async def verify():
        async with main.lifespan(main.app):
            events.append("request")
    if failing_stage is None:
        asyncio.run(verify())
    else:
        with pytest.raises(RuntimeError):
            asyncio.run(verify())
    assert events == ["request", "runs", "models", "redis"]


@pytest.mark.skipif(not os.environ.get("RUN_REDIS_INTEGRATION"), reason="opt-in local Redis")
def test_real_redis_pool_recreated_across_lifespans_without_losing_session(monkeypatch):
    from redis.asyncio import Redis
    url = os.environ["RUN_REDIS_INTEGRATION"]
    service = session_service.SessionService()
    monkeypatch.setattr(session_service, "get_settings", lambda: SimpleNamespace(
        redis_enabled=True, redis_url=url, auth_session_ttl_seconds=60))
    monkeypatch.setattr(main, "sessions", service)
    async def noop():
        pass
    monkeypatch.setattr(main, "close_active_runs", noop)
    monkeypatch.setattr(main, "close_async_clients", noop)
    tokens, clients = [], []
    async def lifespan():
        async with main.lifespan(main.app):
            if tokens:
                record = await service.read(tokens[0])
                assert record.user_id == -999999
            token, ttl = await service.issue(-999999)
            tokens.append(token)
            clients.append(service._redis)
            assert ttl == 60
        assert service._redis is None
    async def cleanup():
        client = Redis.from_url(url)
        try:
            if tokens:
                await client.delete(*["lawpath:auth:" + token for token in tokens])
        finally:
            await client.aclose()
    try:
        asyncio.run(lifespan())
        asyncio.run(lifespan())
        assert len(clients) == 2 and clients[0] is not clients[1]
    finally:
        asyncio.run(cleanup())


def test_cancelled_lifespan_still_closes_every_resource(monkeypatch):
    events = []
    def cleanup(stage):
        async def close():
            await asyncio.sleep(0)
            events.append(stage)
        return close
    monkeypatch.setattr(main, "close_active_runs", cleanup("runs"))
    monkeypatch.setattr(main, "close_async_clients", cleanup("models"))
    monkeypatch.setattr(main, "sessions", SimpleNamespace(close=cleanup("redis")))
    async def verify():
        started = asyncio.Event()
        async def server():
            async with main.lifespan(main.app):
                started.set()
                await asyncio.Event().wait()
        task = asyncio.create_task(server())
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    asyncio.run(verify())
    assert events == ["runs", "models", "redis"]
