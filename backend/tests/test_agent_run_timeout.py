import asyncio
from copy import deepcopy
from types import SimpleNamespace

import pytest

from backend.app.services import agent_run_service
from backend.app.services.agent_run_store import SnapshotConflictError
from backend.app.services.mock_store import store


def test_run_timeout_becomes_terminal_and_is_saved(monkeypatch):
    run_id = 'timeout-check'
    run = {'run_id': run_id, 'status': 'running', 'events': [], 'error': None}
    store.agent_runs[run_id] = run
    saved = []

    async def slow(_):
        await asyncio.sleep(1)

    async def snapshot(value):
        saved.append(value['status'])

    monkeypatch.setattr(agent_run_service, '_execute_run', slow)
    monkeypatch.setattr(agent_run_service, 'save_snapshot', snapshot)
    monkeypatch.setattr(agent_run_service, 'persistent_runs_enabled', lambda: False)
    monkeypatch.setattr(agent_run_service, 'get_settings', lambda: SimpleNamespace(agent_run_timeout_seconds=0.01))
    try:
        asyncio.run(agent_run_service.execute_run(run_id))
        assert run['status'] == 'failed'
        assert run['error']['code'] == 'ANALYSIS_TIMEOUT'
        assert run['events'][-1]['event'] == 'run.failed'
        assert saved == ['failed']
    finally:
        store.agent_runs.pop(run_id, None)


@pytest.mark.parametrize("stage", ["start", "progress", "finish"])
def test_conflicting_writer_stops_without_replacing_authoritative_completion(monkeypatch, stage):
    run, _ = agent_run_service.create_run(
        {"id": "conflict-owner", "role": "GUEST"}, "housing", "synthetic", stage,
        cache_enabled=False)
    run_id = run["run_id"]
    latest = dict(deepcopy(run), status="completed", revision=7,
                  result={"answer": "authoritative"})
    writes = []
    generated = []

    async def snapshot(value):
        writes.append(value["status"])
        conflict = stage == "start" or (stage == "progress" and len(writes) == 2)
        conflict = conflict or (stage == "finish" and value["status"] == "completed")
        if conflict:
            raise SnapshotConflictError(latest, "revision")

    async def answer(request, event_callback):
        generated.append(True)
        await event_callback({"stage": "validation_started"})
        return SimpleNamespace(termination_reason="model_finished", model_dump=lambda **_: {"answer": "local"})

    async def guest_save(*args):
        return None

    monkeypatch.setattr(agent_run_service, "save_snapshot", snapshot)
    monkeypatch.setattr(agent_run_service, "answer_question_from_mcp", answer)
    monkeypatch.setattr(agent_run_service, "log_result", lambda *args: None)
    monkeypatch.setattr(agent_run_service.guest_sessions, "save_analysis", guest_save)
    monkeypatch.setattr(agent_run_service, "persistent_runs_enabled", lambda: True)
    asyncio.run(agent_run_service.execute_run(run_id))
    assert run == latest
    assert "failed" not in writes
    assert len(writes) == {"start": 1, "progress": 2, "finish": 3}[stage]
    assert bool(generated) == (stage != "start")
    assert run_id not in store.agent_runs


def test_timeout_failure_write_conflict_preserves_completed_result(monkeypatch):
    run_id = "timeout-conflict"
    run = {"run_id": run_id, "status": "running", "events": []}
    store.agent_runs[run_id] = run
    latest = dict(run, status="completed", result={"answer": "preserved"}, events=[])

    async def slow(_):
        await asyncio.sleep(1)

    async def snapshot(_):
        raise SnapshotConflictError(latest, "revision")

    monkeypatch.setattr(agent_run_service, "_execute_run", slow)
    monkeypatch.setattr(agent_run_service, "save_snapshot", snapshot)
    monkeypatch.setattr(agent_run_service, "get_settings", lambda: SimpleNamespace(agent_run_timeout_seconds=0.01))
    asyncio.run(agent_run_service.execute_run(run_id))
    assert run == latest
    assert run_id not in store.agent_runs
