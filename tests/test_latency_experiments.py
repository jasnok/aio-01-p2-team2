from scripts.compare_latency import experiment_settings
from backend.app.core.config import get_settings


def test_experimental_settings_are_restored_after_failure(monkeypatch):
    import os
    import pytest
    monkeypatch.setenv("ANSWER_REPAIR_ATTEMPTS", "1")
    with pytest.raises(RuntimeError):
        with experiment_settings({"answer_repair_attempts": 0, "answer_reasoning_effort": "low"}) as settings:
            assert settings.answer_repair_attempts == 0 and settings.answer_reasoning_effort == "low"
            raise RuntimeError("synthetic failure")
    assert os.environ["ANSWER_REPAIR_ATTEMPTS"] == "1"
    assert get_settings().answer_repair_attempts == 1


def test_cold_cache_records_process_restart_identity(monkeypatch):
    from scripts import benchmark_cache as cache
    from types import SimpleNamespace
    commands = []
    def run(args, **kwargs):
        commands.append(args)
        return SimpleNamespace(returncode=0)
    def output(args, **kwargs):
        commands.append(args)
        if args[:2] == ["docker", "inspect"]:
            return '{"Health":{"Status":"healthy"},"StartedAt":"synthetic-start"}'
        return "synthetic-container"
    monkeypatch.setattr(cache.subprocess, "run", run)
    monkeypatch.setattr(cache.subprocess, "check_output", output)
    result = cache.cold_cache()
    assert commands[0] == ["docker", "compose", "restart", "mcp-server"]
    assert result["started_at"] == "synthetic-start" and result["health"] == "healthy"
