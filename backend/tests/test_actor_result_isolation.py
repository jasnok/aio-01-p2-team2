import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.app.routers import mock_api, legal
from backend.app.schemas.legal import LegalQuestionRequest, LegalQuestionResponse
from backend.app.services import agent_run_service, legal_term_run_store, agent_run_store
from backend.app.services.actor_identity import actor_key
from backend.app.services.mock_store import store

MEMBER = {"id": "same-id", "role": "USER"}
GUEST = {"id": "same-id", "role": "GUEST"}


def test_run_read_and_save_require_principal_kind(monkeypatch):
    monkeypatch.setattr(mock_api.agent_run_store, "enabled", lambda: False)
    run, _ = agent_run_service.create_run(MEMBER, "housing", "synthetic question", "key", cache_enabled=False)
    async def verify():
        assert await mock_api.get_run(run["run_id"], MEMBER) is run
        assert await mock_api.get_run_for_save(run["run_id"], MEMBER) is run
        for method, status in [(mock_api.get_run, 404), (mock_api.get_run_for_save, 403)]:
            with pytest.raises(HTTPException) as caught:
                await method(run["run_id"], GUEST)
            assert caught.value.status_code == status
    try:
        asyncio.run(verify())
    finally:
        store.agent_runs.pop(run["run_id"], None)


def test_in_memory_reservations_separate_member_and_guest():
    runs = []
    try:
        for owner in (MEMBER, GUEST):
            run, created = agent_run_service.create_run(owner, "housing", "synthetic question", "isolation")
            assert created
            runs.append(run)
            repeated, created = agent_run_service.create_run(owner, "housing", "synthetic question", "isolation")
            assert not created and repeated is run
        assert runs[0]["run_id"] != runs[1]["run_id"]
    finally:
        for run in runs:
            store.agent_runs.pop(run["run_id"], None)
        for owner in (MEMBER, GUEST):
            store.agent_run_idempotency.pop((actor_key(owner), "isolation"), None)


def test_term_run_requires_principal_kind(monkeypatch):
    monkeypatch.setattr(legal_term_run_store, "get_settings", lambda: SimpleNamespace(redis_enabled=False, term_run_ttl_seconds=60))
    service = legal_term_run_store.LegalTermRunStore()
    async def verify():
        await service.remember(actor=MEMBER, request_id="term-test", question="synthetic", answer="synthetic", conversation_id=None)
        assert (await service.get_for_actor("term-test", MEMBER))["owner_role"] == "USER"
        with pytest.raises(legal_term_run_store.LegalTermRunForbiddenError):
            await service.get_for_actor("term-test", GUEST)
        assert await service.get_for_actor("term-test", dict(MEMBER, role="ADMIN"))
    asyncio.run(verify())


def test_sync_question_cache_binds_principal_and_input(monkeypatch):
    monkeypatch.setattr(legal, "get_settings", lambda: SimpleNamespace(backend_mock_mode=True))
    generated = []
    def answer(request):
        generated.append(request.question)
        return LegalQuestionResponse(request_id=f"req-{len(generated)}", agent_id=request.category,
            termination_reason="model_finished", question_summary="synthetic", answer="synthetic")
    monkeypatch.setattr(legal, "answer_question", answer)
    async def guest_save(*args, **kwargs):
        pass
    monkeypatch.setattr(legal.guest_sessions, "save_analysis", guest_save)
    request = LegalQuestionRequest(session_id="synthetic", category="housing", question="synthetic first question")
    async def call(owner, body=request):
        return await legal.create_question(body, "sync-isolation", None, None, owner)
    async def verify():
        first = await call(MEMBER)
        assert (await call(MEMBER)).request_id == first.request_id
        assert (await call(GUEST)).request_id != first.request_id
        with pytest.raises(HTTPException) as caught:
            await call(MEMBER, request.model_copy(update={"question": "synthetic second question"}))
        assert caught.value.status_code == 409
        assert len(generated) == 2
    try:
        asyncio.run(verify())
    finally:
        for owner in (MEMBER, GUEST):
            store.idempotency.pop((actor_key(owner), "/api/legal/questions", "sync-isolation"), None)


def test_redis_key_separates_principals_and_unifies_member_roles():
    assert agent_run_store.reservation_key(MEMBER, "key") != agent_run_store.reservation_key(GUEST, "key")
    assert agent_run_store.reservation_key(MEMBER, "key") == agent_run_store.reservation_key(dict(MEMBER, role="ADMIN"), "key")


@pytest.mark.skipif(not __import__("os").environ.get("RUN_REDIS_INTEGRATION"), reason="opt-in local Redis")
def test_real_redis_reservations_and_legacy_records_are_principal_safe(monkeypatch):
    import os, json, hashlib, uuid
    from redis.asyncio import Redis
    async def verify():
        client = Redis.from_url(os.environ["RUN_REDIS_INTEGRATION"], decode_responses=True)
        async def redis_client():
            return client
        monkeypatch.setattr(agent_run_store.sessions, "_redis_client", redis_client)
        monkeypatch.setattr(agent_run_store, "get_settings", lambda: SimpleNamespace(agent_run_ttl_seconds=60, redis_enabled=True, backend_mock_mode=False))
        identity = uuid.uuid4().hex
        member = dict(MEMBER, id=identity)
        guest = dict(GUEST, id=identity)
        fingerprint = ["housing", "synthetic question", False, None]
        records = [{"run_id": uuid.uuid4().hex, "owner_id": identity, "actor": owner,
                    "status": "completed", "revision": 0} for owner in (member, guest)]
        legacy_key = "lawpath:run-idempotency:" + hashlib.sha256(json.dumps([identity, "legacy"]).encode()).hexdigest()
        keys = [legacy_key] + [agent_run_store.reservation_key(owner, key)
            for owner in (member, guest) for key in ("key", "legacy")]
        keys += [f"lawpath:run:{record['run_id']}" for record in records]
        term_id = uuid.uuid4().hex
        keys.append(legal_term_run_store.LegalTermRunStore._key(term_id))
        try:
            reservations = await asyncio.gather(*[agent_run_store.reserve_run(record, fingerprint, "key") for record in records])
            assert all(created for _, created in reservations)
            for owner, record in zip((member, guest), records):
                assert (await agent_run_store.find_reserved_run(owner, fingerprint, "key"))["run_id"] == record["run_id"]
                replay, created = await agent_run_store.reserve_run(dict(record, run_id="unused"), fingerprint, "key")
                assert not created and replay["run_id"] == record["run_id"]
            await client.set(legacy_key, json.dumps({"run_id": records[0]["run_id"], "fingerprint": fingerprint}), ex=60)
            assert (await agent_run_store.find_reserved_run(member, fingerprint, "legacy"))["run_id"] == records[0]["run_id"]
            assert await agent_run_store.find_reserved_run(guest, fingerprint, "legacy") is None
            wrong = ["labor", "different", False, None]
            with pytest.raises(ValueError, match="IDEMPOTENCY_CONFLICT"):
                await agent_run_store.find_reserved_run(member, wrong, "legacy")
            assert await agent_run_store.find_reserved_run(guest, wrong, "legacy") is None
            assert 0 < await client.ttl(legacy_key) <= 60
            monkeypatch.setattr(legal_term_run_store, "get_settings", lambda: SimpleNamespace(redis_enabled=True, term_run_ttl_seconds=60))
            terms = legal_term_run_store.LegalTermRunStore()
            await terms.remember(actor=member, request_id=term_id, question="synthetic", answer="synthetic", conversation_id=None)
            assert (await terms.get_for_actor(term_id, member))["owner_role"] == "USER"
            with pytest.raises(legal_term_run_store.LegalTermRunForbiddenError):
                await terms.get_for_actor(term_id, guest)
        finally:
            await client.delete(*keys)
            await client.aclose()
    asyncio.run(verify())
