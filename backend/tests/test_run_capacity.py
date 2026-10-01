import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.app.services import agent_run_service, run_capacity as capacity_module
from backend.app.routers import mock_api
from backend.app.services.mock_store import store
from backend.app.services.actor_identity import actor_key
from backend.app.services.session_service import SessionStoreUnavailableError


def configure(monkeypatch):
    capacity = capacity_module.RunCapacity()
    monkeypatch.setattr(capacity_module, "get_settings", lambda: SimpleNamespace(agent_run_max_concurrency=2))
    monkeypatch.setattr(agent_run_service, "run_capacity", capacity)
    monkeypatch.setattr(mock_api, "run_capacity", capacity)
    return capacity


def test_bounded_tasks_release_on_completion_and_shutdown(monkeypatch):
    capacity = configure(monkeypatch)
    async def verify():
        gate = asyncio.Event()
        async def hold(_):
            await gate.wait()
        monkeypatch.setattr(agent_run_service, "execute_run", hold)
        tasks = [agent_run_service.start_run(str(i)) for i in range(2)]
        with pytest.raises(capacity_module.RunCapacityError):
            agent_run_service.start_run("overflow")
        assert capacity.used == 2
        await agent_run_service.close_active_runs()
        assert all(task.cancelled() for task in tasks)
        assert capacity.used == 0
        task = agent_run_service.start_run("new")
        gate.set()
        await task
        await asyncio.sleep(0)
        assert capacity.used == 0
    asyncio.run(verify())


def test_synthetic_25_request_burst_is_bounded_without_slot_leaks(monkeypatch):
    capacity = configure(monkeypatch)
    async def verify():
        gate = asyncio.Event()
        async def hold(_):
            await gate.wait()
        monkeypatch.setattr(agent_run_service, "execute_run", hold)
        admitted = []
        rejected = 0
        for index in range(25):
            try:
                admitted.append(agent_run_service.start_run(str(index)))
            except capacity_module.RunCapacityError:
                rejected += 1
        assert len(admitted) == 2 and rejected == 23 and capacity.used == 2
        gate.set()
        await asyncio.gather(*admitted)
        await asyncio.sleep(0)
        assert capacity.used == 0
    asyncio.run(verify())


def test_capacity_response_and_mock_duplicate_at_capacity(monkeypatch):
    capacity = configure(monkeypatch)
    monkeypatch.setattr(mock_api.agent_run_store, "enabled", lambda: False)
    slots = []
    def start(_, slot):
        slots.append(slot)
    monkeypatch.setattr(mock_api, "start_run", start)
    owner = {"id": "capacity-test", "role": "GUEST"}
    body = mock_api.AgentRunCreate(category="housing", question="synthetic question")
    async def verify():
        first = await mock_api.create_agent_run(body, "first", owner)
        await mock_api.create_agent_run(body, "second", owner)
        assert await mock_api.create_agent_run(body, "first", owner) == first
        with pytest.raises(HTTPException) as error:
            await mock_api.create_agent_run(body, "third", owner)
        assert error.value.status_code == 503
        assert error.value.headers == {"Retry-After": "2"}
        assert capacity.used == 2
        assert (actor_key(owner), "third") not in store.agent_run_idempotency
    try:
        asyncio.run(verify())
    finally:
        for slot in slots:
            slot.release()
        for key in list(store.agent_run_idempotency):
            if key[0] == actor_key(owner):
                store.agent_runs.pop(store.agent_run_idempotency.pop(key)["run_id"], None)
    assert capacity.used == 0


def test_redis_reservation_error_and_duplicate_release_slot(monkeypatch):
    capacity = configure(monkeypatch)
    monkeypatch.setattr(mock_api.agent_run_store, "enabled", lambda: True)
    async def absent(*args):
        return None
    monkeypatch.setattr(mock_api.agent_run_store, "find_reserved_run", absent)
    owner = {"id": "capacity-redis", "role": "GUEST"}
    body = mock_api.AgentRunCreate(category="housing", question="synthetic question")
    async def outage(*args):
        assert capacity.used == 1
        raise SessionStoreUnavailableError()
    monkeypatch.setattr(mock_api.agent_run_store, "reserve_run", outage)
    with pytest.raises(HTTPException) as error:
        asyncio.run(mock_api.create_agent_run(body, "error", owner))
    assert error.value.status_code == 503 and capacity.used == 0
    async def duplicate(run, *args):
        return {"run_id": "existing", "status": "running"}, False
    monkeypatch.setattr(mock_api.agent_run_store, "reserve_run", duplicate)
    assert asyncio.run(mock_api.create_agent_run(body, "duplicate", owner))["run_id"] == "existing"
    assert capacity.used == 0
    async def existing(*args):
        return {"run_id": "existing", "status": "completed"}
    monkeypatch.setattr(mock_api.agent_run_store, "find_reserved_run", existing)
    slots = [capacity.acquire(), capacity.acquire()]
    try:
        assert asyncio.run(mock_api.create_agent_run(body, "existing", owner))["status"] == "completed"
    finally:
        for slot in slots:
            slot.release()


def test_cancel_during_reservation_releases_admission_and_local_state(monkeypatch):
    capacity = configure(monkeypatch)
    monkeypatch.setattr(mock_api.agent_run_store, "enabled", lambda: True)
    async def absent(*args):
        return None
    monkeypatch.setattr(mock_api.agent_run_store, "find_reserved_run", absent)
    async def verify():
        entered = asyncio.Event()
        run_ids = []
        async def reserve(run, *args):
            run_ids.append(run["run_id"])
            entered.set()
            await asyncio.Event().wait()
        monkeypatch.setattr(mock_api.agent_run_store, "reserve_run", reserve)
        task = asyncio.create_task(mock_api.create_agent_run(
            mock_api.AgentRunCreate(category="housing", question="synthetic question"),
            "cancel", {"id": "capacity-cancel", "role": "GUEST"}))
        await entered.wait()
        assert capacity.used == 1
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert capacity.used == 0
        assert run_ids[0] not in store.agent_runs
    asyncio.run(verify())
