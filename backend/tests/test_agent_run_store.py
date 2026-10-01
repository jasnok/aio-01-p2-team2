import asyncio
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from backend.app.services import agent_run_store
from backend.app.services.session_service import SessionStoreUnavailableError


def configure(monkeypatch, client):
    monkeypatch.setattr(agent_run_store, "get_settings", lambda: SimpleNamespace(
        redis_enabled=True, backend_mock_mode=False, agent_run_ttl_seconds=86400,
        agent_run_timeout_seconds=150))
    async def redis_client():
        return client
    monkeypatch.setattr(agent_run_store.sessions, "_redis_client", redis_client)


def make_run(status="completed", age=0):
    return {"run_id": "test-run", "owner_id": "owner", "status": status, "events": [],
            "created_at": (datetime.now(timezone.utc) - timedelta(seconds=age)).isoformat()}


def test_snapshot_restores_without_process_memory_and_retains_ttl(monkeypatch):
    class Redis:
        values = {}
        async def set(self, key, value, ex):
            assert ex == 86400
            self.values[key] = value
        async def get(self, key):
            return self.values.get(key)
    client = Redis()
    configure(monkeypatch, client)
    run = make_run()
    asyncio.run(agent_run_store.save_snapshot(run))
    assert asyncio.run(agent_run_store.read_snapshot("test-run")) == run


def test_abandoned_run_becomes_failed_instead_of_polling_forever(monkeypatch):
    class Redis:
        raw = json.dumps(make_run("running", 200))
        async def get(self, key):
            return self.raw
        async def eval(self, script, count, key, expected, value):
            assert 'KEEPTTL' in script
            assert count == 1
            if self.raw == expected:
                self.raw = value
            return self.raw
    configure(monkeypatch, Redis())
    run = asyncio.run(agent_run_store.read_snapshot("test-run"))
    assert run["status"] == "failed"
    assert run["error"]["code"] == "ANALYSIS_INTERRUPTED"
    assert run["events"][-1]["event"] == "run.failed"


@pytest.mark.parametrize("winner", ["completed", "running", None])
def test_timeout_poll_returns_concurrent_update_or_expiration(monkeypatch, winner):
    old = json.dumps(make_run("running", 200))
    latest = make_run(winner) if winner else None
    if latest:
        latest["result"] = {"answer": "preserved"}

    class Redis:
        async def get(self, key):
            return old

        async def eval(self, script, count, key, expected, value):
            assert expected == old
            # Simulate a worker update or key expiry after GET, before Lua.
            return json.dumps(latest) if latest else ""

    configure(monkeypatch, Redis())
    assert asyncio.run(agent_run_store.read_snapshot("test-run")) == latest


def test_redis_outage_raises_service_error_without_connection_details(monkeypatch):
    class Redis:
        async def get(self, key):
            raise ConnectionError("private connection string")
    configure(monkeypatch, Redis())
    with pytest.raises(SessionStoreUnavailableError) as error:
        asyncio.run(agent_run_store.read_snapshot("test-run"))
    assert "private" not in str(error.value)


@pytest.mark.skipif(not os.getenv("RUN_REDIS_INTEGRATION"), reason="requires an explicit Redis test URL")
def test_real_redis_timeout_compare_and_set_preserves_winner_and_ttl(monkeypatch):
    from redis.asyncio import Redis

    async def verify():
        client = Redis.from_url(os.environ["RUN_REDIS_INTEGRATION"], decode_responses=True)
        run_id = "timeout-test-" + uuid.uuid4().hex
        key = f"lawpath:run:{run_id}"
        run = make_run("running", 200)
        run["run_id"] = run_id
        raw = json.dumps(run)
        completed = dict(run, status="completed", result={"answer": "preserved"})

        class Poller:
            async def get(self, requested):
                observed = await client.get(requested)
                await client.set(key, json.dumps(completed), keepttl=True)
                return observed

            async def eval(self, *args):
                return await client.eval(*args)

        try:
            await client.set(key, raw, ex=30)
            configure(monkeypatch, Poller())
            assert await agent_run_store.read_snapshot(run_id) == completed
            assert json.loads(await client.get(key)) == completed
            await client.set(key, raw, ex=30)
            before = await client.pttl(key)
            configure(monkeypatch, client)
            assert (await agent_run_store.read_snapshot(run_id))["status"] == "failed"
            assert 0 < await client.pttl(key) <= before
            await client.delete(key)
            assert await client.eval(agent_run_store._INTERRUPT_SNAPSHOT, 1, key, raw, raw) == ""
            assert not await client.exists(key)
        finally:
            await client.delete(key)
            await client.aclose()

    asyncio.run(verify())
