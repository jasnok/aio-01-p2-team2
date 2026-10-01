import asyncio
import json
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
        async def set(self, key, value, ex):
            self.raw = value
    configure(monkeypatch, Redis())
    run = asyncio.run(agent_run_store.read_snapshot("test-run"))
    assert run["status"] == "failed"
    assert run["error"]["code"] == "ANALYSIS_INTERRUPTED"
    assert run["events"][-1]["event"] == "run.failed"


def test_redis_outage_raises_service_error_without_connection_details(monkeypatch):
    class Redis:
        async def get(self, key):
            raise ConnectionError("private connection string")
    configure(monkeypatch, Redis())
    with pytest.raises(SessionStoreUnavailableError) as error:
        asyncio.run(agent_run_store.read_snapshot("test-run"))
    assert "private" not in str(error.value)
