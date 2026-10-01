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
        values = {"lawpath:run:test-run": json.dumps(make_run())}
        async def get(self, key):
            return self.values.get(key)
    client = Redis()
    configure(monkeypatch, client)
    assert asyncio.run(agent_run_store.read_snapshot("test-run"))["status"] == "completed"


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
            interrupted = await agent_run_store.read_snapshot(run_id)
            assert interrupted["status"] == "failed"
            assert interrupted["revision"] == 1  # legacy snapshots start at revision zero
            assert 0 < await client.pttl(key) <= before
            await client.delete(key)
            assert await client.eval(agent_run_store._INTERRUPT_SNAPSHOT, 1, key, raw, raw) == ""
            assert not await client.exists(key)
        finally:
            await client.delete(key)
            await client.aclose()

    asyncio.run(verify())


@pytest.mark.skipif(not os.getenv("RUN_REDIS_INTEGRATION"), reason="requires an explicit Redis test URL")
def test_real_redis_revision_transitions_and_reservation(monkeypatch):
    from copy import deepcopy
    import hashlib
    from redis.asyncio import Redis

    async def verify():
        client = Redis.from_url(os.environ["RUN_REDIS_INTEGRATION"], decode_responses=True)
        owner = "revision-test-" + uuid.uuid4().hex
        idempotency = uuid.uuid4().hex
        fingerprint = ["housing", "synthetic question", False, None]
        runs = [dict(make_run("queued"), run_id=owner + str(i), owner_id=owner) for i in range(2)]
        reservation = "lawpath:run-idempotency:" + hashlib.sha256(
            json.dumps([owner, idempotency]).encode()).hexdigest()
        keys = [reservation] + [f"lawpath:run:{run['run_id']}" for run in runs]
        configure(monkeypatch, client)

        async def rejected(candidate, reason):
            before = await client.get(f"lawpath:run:{candidate['run_id']}")
            with pytest.raises(agent_run_store.SnapshotConflictError) as error:
                await agent_run_store.save_snapshot(candidate)
            assert error.value.reason == reason
            assert await client.get(f"lawpath:run:{candidate['run_id']}") == before

        try:
            reservations = await asyncio.gather(*[
                agent_run_store.reserve_run(run, fingerprint, idempotency) for run in runs])
            assert sum(created for _, created in reservations) == 1
            assert reservations[0][0]["run_id"] == reservations[1][0]["run_id"]
            run = next(run for run, created in reservations if created)
            assert run["revision"] == 1
            queued = deepcopy(run)
            run["status"] = "running"
            run["events"] = [{"id": 1, "event": "run.started", "data": {}}]
            await agent_run_store.save_snapshot(run)
            assert run["revision"] == 2
            await rejected(queued, "revision")
            await rejected(dict(run, owner_id="different"), "identity")
            await rejected(dict(run, status="queued"), "transition")
            await rejected(dict(run, events=[]), "events")
            altered = deepcopy(run)
            altered["events"][0]["event"] = "rewritten"
            await rejected(altered, "events")
            await rejected(dict(run, events=run["events"] + [{"id": 3}]), "events")
            await rejected(dict(run, status="completed"), "result")
            await rejected(dict(run, status="failed"), "error")
            stale = deepcopy(run)
            run.update(status="completed", result={"answer": "preserved", "claims": [], "nested": {"items": []}})
            run["events"].append({"id": 2, "event": "run.completed", "data": {}})
            await agent_run_store.save_snapshot(run)
            assert run["revision"] == 3
            restored = await agent_run_store.read_snapshot(run["run_id"])
            assert restored["result"]["claims"] == []
            assert restored["result"]["nested"]["items"] == []
            await rejected(stale, "revision")
            await rejected(dict(run, status="failed", error={"code": "late"}), "terminal")
            before = await client.pttl(f"lawpath:run:{run['run_id']}")
            await agent_run_store.save_snapshot(run)  # identical terminal save is a no-op
            assert run["revision"] == 3
            assert 0 < await client.pttl(f"lawpath:run:{run['run_id']}") <= before
            for terminal in ("stopped", "failed"):
                await client.set(f"lawpath:run:{run['run_id']}", json.dumps(stale), ex=30)
                ending = dict(deepcopy(stale), status=terminal, result={"answer": "retained"},
                              error={"code": "synthetic"} if terminal == "failed" else None)
                await agent_run_store.save_snapshot(ending)
                await rejected(dict(ending, status="running"), "terminal")
            legacy = deepcopy(stale)
            legacy.pop("revision")
            await client.set(f"lawpath:run:{run['run_id']}", json.dumps(legacy), ex=30)
            await agent_run_store.save_snapshot(legacy)
            assert legacy["revision"] == 1
            candidates = [deepcopy(legacy), deepcopy(legacy)]
            for index, candidate in enumerate(candidates):
                candidate["events"].append({"id": 2, "event": "step.completed", "data": {"winner": index}})
            outcomes = await asyncio.gather(*[
                agent_run_store.save_snapshot(candidate) for candidate in candidates], return_exceptions=True)
            assert sum(isinstance(item, agent_run_store.SnapshotConflictError) for item in outcomes) == 1
            assert sum(item is None for item in outcomes) == 1
            stored = await agent_run_store.read_snapshot(run["run_id"])
            assert stored["revision"] == 2
            assert len(stored["events"]) == 2
            await client.pexpire(f"lawpath:run:{run['run_id']}", 1)
            await asyncio.sleep(0.01)
            await rejected(run, "expired")
        finally:
            await client.delete(*keys)
            await client.aclose()

    asyncio.run(verify())
