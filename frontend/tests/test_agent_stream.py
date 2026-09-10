import json
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from frontend.clients import agent_stream as stream
from frontend.clients.backend_client import BackendClientError
from frontend.components.law_card import law_preview
from frontend.services.api_legal_service import ApiLegalService


def snapshot(status="completed"):
    return {"run_id": "r1", "status": status, "result": {
        "request_id": "q1", "agent_id": "housing", "status": status,
        "termination_reason": "needs_clarification" if status == "stopped" else "model_finished",
        "question_summary": "summary", "answer": "answer", "is_mock": False,
    }}


def test_preview_preserves_full_analysis_and_limits_length():
    content = "법령 본문\n" * 100
    raw = snapshot()["result"]
    raw["related_laws"] = [{"title": "law", "content": content}]
    adapted = ApiLegalService.adapt_analysis(raw, "question")
    law = adapted["related_laws"][0]
    assert len(law_preview(law)) == 150
    assert law_preview(law).endswith("…")
    assert "\n" not in law_preview(law)
    assert law["content"] == law["detail"] == content
    assert law_preview({"summary": "short", "content": content}) == "short"
    assert len(law_preview({"content": "x" * 150})) == 150
    assert law_preview({})


def test_parser_heartbeat_multiline_and_incomplete_frame():
    frames = list(stream.parse_sse([
        ": heartbeat", "", "id: 1", "event: step.started",
        'data: {"run_id": "r1",', 'data: "message": "검색"}', "",
        "id: 2", 'data: {"incomplete": true}',
    ]))
    assert frames == [("1", "step.started", {"run_id": "r1", "message": "검색"})]


def setup(monkeypatch):
    monkeypatch.setattr(stream, "get_frontend_settings", lambda: SimpleNamespace(
        normalized_backend_url="http://backend", frontend_sse_total_timeout_seconds=180))


def test_reconnect_deduplicates_and_sends_last_event_id(monkeypatch):
    setup(monkeypatch)
    snapshots = iter([{"run_id": "r1", "status": "running"},
                      {"run_id": "r1", "status": "running"}, snapshot()])
    monkeypatch.setattr(stream.api, "get_agent_run", lambda *a: next(snapshots))
    requests, seen = [], []
    @contextmanager
    def connect(*args, **kwargs):
        requests.append(dict(kwargs["headers"]))
        number = len(requests)
        class Response:
            headers = {"content-type": "text/event-stream"}
            def raise_for_status(self): pass
            def iter_lines(self):
                yield from ["id: 1", "event: step.started",
                            'data: {"run_id":"r1","step_id":"laws","message":"검색"}', ""]
                if number == 2:
                    yield from ["id: 2", "event: run.completed", 'data: {"run_id":"r1"}', ""]
        yield Response()
    monkeypatch.setattr(stream.httpx, "stream", connect)
    result = stream.receive_run("token", "guest", "r1", on_event=lambda *e: seen.append(e))
    assert result["request_id"] == "q1"
    assert [e[0] for e in seen] == [1, 2]
    assert requests[1]["Last-Event-ID"] == "1"
    assert requests[0]["Authorization"] == "Bearer token"


def test_snapshot_recovers_completed_or_clarification_without_stream(monkeypatch):
    setup(monkeypatch)
    for status in ["completed", "stopped"]:
        monkeypatch.setattr(stream.api, "get_agent_run", lambda *a: snapshot(status))
        result = stream.receive_run(None, "guest", "r1")
        assert result["status"] == status
        if status == "stopped":
            assert ApiLegalService.adapt_analysis(result, "question")["result_state"] == "needs_clarification"


def test_failed_and_invalid_final_response():
    with pytest.raises(BackendClientError, match="실패"):
        stream.final_result({"run_id": "r1", "status": "failed"}, "r1")
    for data in [{"run_id": "other"}, {"run_id": "r1", "status": "completed", "result": {}},
                 {"run_id": "r1", "status": "unknown"}]:
        with pytest.raises(BackendClientError):
            stream.final_result(data, "r1")


def test_reconnection_limit(monkeypatch):
    setup(monkeypatch)
    monkeypatch.setattr(stream.api, "get_agent_run", lambda *a: {"run_id": "r1", "status": "running"})
    calls = []
    @contextmanager
    def connect(*a, **kw):
        calls.append(1)
        raise stream.httpx.ConnectError("offline")
        yield
    monkeypatch.setattr(stream.httpx, "stream", connect)
    with pytest.raises(BackendClientError, match="기존 작업"):
        stream.receive_run(None, "guest", "r1")
    assert len(calls) == 3
