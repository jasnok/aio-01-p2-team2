import asyncio
import json
import os
import uuid

import pytest

from backend.app.services import guest_session_service
from backend.app.services.guest_session_service import GuestSessionService
from backend.app.services.session_service import SessionStoreUnavailableError


def memory_settings():
    return type("Settings", (), {"redis_enabled": False, "guest_session_ttl_seconds": 3600})()


def run(run_id: str) -> dict:
    return {
        "run_id": run_id,
        "category": "consumer",
        "question": "중고거래 환불을 받고 싶어요.",
        "status": "completed",
        "result": {"answer": "임시 답변"},
        "updated_at": "2026-09-09T00:00:00+00:00",
    }


def test_guest_history_is_ttl_bound_and_never_uses_a_database(monkeypatch) -> None:
    monkeypatch.setattr(guest_session_service, "get_settings", memory_settings)
    service = GuestSessionService()

    assert asyncio.run(service.save_analysis("guest-1", run("run-1"))) == 3600
    items, expires_in = asyncio.run(service.list_analyses("guest-1"))

    assert [item["run_id"] for item in items] == ["run-1"]
    assert 0 < expires_in <= 3600
    asyncio.run(service.clear("guest-1"))
    assert asyncio.run(service.list_analyses("guest-1"))[0] == []


def test_guest_history_replaces_a_retry_with_the_same_run_id(monkeypatch) -> None:
    monkeypatch.setattr(guest_session_service, "get_settings", memory_settings)
    service = GuestSessionService()

    asyncio.run(service.save_analysis("guest-1", run("run-1")))
    changed = run("run-1")
    changed["result"] = {"answer": "재시도 결과"}
    asyncio.run(service.save_analysis("guest-1", changed))

    items, _ = asyncio.run(service.list_analyses("guest-1"))
    assert len(items) == 1
    assert items[0]["result"]["answer"] == "재시도 결과"


def configure_redis(monkeypatch, client):
    settings = memory_settings()
    settings.redis_enabled = True
    monkeypatch.setattr(guest_session_service, "get_settings", lambda: settings)
    async def redis_client():
        return client
    monkeypatch.setattr(guest_session_service.sessions, "_redis_client", redis_client)


def test_contention_is_bounded_and_does_not_report_a_successful_save(monkeypatch):
    class Redis:
        attempts = 0
        async def get(self, key):
            return "[]"
        async def eval(self, *args):
            self.attempts += 1
            return 0
    client = Redis()
    configure_redis(monkeypatch, client)
    with pytest.raises(SessionStoreUnavailableError):
        asyncio.run(GuestSessionService().save_analysis("guest", run("test")))
    assert client.attempts == 8


def test_connection_error_does_not_expose_private_details(monkeypatch):
    class Redis:
        async def get(self, key):
            raise ConnectionError("private redis credentials")
    configure_redis(monkeypatch, Redis())
    with pytest.raises(SessionStoreUnavailableError) as error:
        asyncio.run(GuestSessionService().save_analysis("guest", run("test")))
    assert "private" not in str(error.value)


@pytest.mark.skipif(not os.getenv("RUN_REDIS_INTEGRATION"), reason="requires an explicit Redis test URL")
def test_real_redis_concurrent_guest_history_preserves_both_records(monkeypatch):
    from redis.asyncio import Redis

    async def verify():
        client = Redis.from_url(os.environ["RUN_REDIS_INTEGRATION"], decode_responses=True)
        guest = "guest-history-test-" + uuid.uuid4().hex
        key = GuestSessionService._key(guest)
        other_key = GuestSessionService._key(guest + "-other")
        barrier = asyncio.Event()

        class ConcurrentRedis:
            reads = 0
            conflicts = 0
            async def get(self, requested):
                observed = await client.get(requested)
                self.reads += 1
                if self.reads <= 2:
                    if self.reads == 2:
                        barrier.set()
                    await barrier.wait()
                return observed
            async def eval(self, *args):
                accepted = await client.eval(*args)
                self.conflicts += int(not accepted)
                return accepted
            async def delete(self, *keys):
                return await client.delete(*keys)

        proxy = ConcurrentRedis()
        configure_redis(monkeypatch, proxy)
        services = [GuestSessionService(), GuestSessionService()]
        first = run("first")
        first["result"] = {"answer": "preserved", "claims": [], "nested": {"items": []}}
        try:
            await asyncio.wait_for(asyncio.gather(
                services[0].save_analysis(guest, first),
                services[1].save_term_chat(guest, run("second"))), timeout=5)
            records = json.loads(await client.get(key))
            assert {item["run_id"] for item in records} == {"first", "second"}
            assert {item["kind"] for item in records} == {"legal_analysis", "legal_term_chat"}
            assert proxy.conflicts == 1
            assert 0 < await client.ttl(key) <= 3600
            retained = next(item for item in records if item["run_id"] == "first")
            assert retained["result"]["claims"] == []
            assert retained["result"]["nested"]["items"] == []
            changed = dict(first, result={"answer": "replacement"})
            await services[0].save_analysis(guest, changed)
            records = json.loads(await client.get(key))
            assert len(records) == 2
            assert records[0]["run_id"] == "first"
            assert records[0]["result"]["answer"] == "replacement"
            await services[1].save_analysis(guest + "-other", run("isolated"))
            assert len(json.loads(await client.get(key))) == 2
            assert json.loads(await client.get(other_key))[0]["run_id"] == "isolated"
            await services[0].clear(guest)
            assert not await client.exists(key)
            assert await client.exists(other_key)
        finally:
            await client.delete(key, other_key)
            await client.aclose()

    asyncio.run(verify())
