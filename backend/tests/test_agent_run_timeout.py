import asyncio
from types import SimpleNamespace

from backend.app.services import agent_run_service
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
