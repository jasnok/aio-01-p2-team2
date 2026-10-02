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


@pytest.mark.parametrize("error_type", [stream.httpx.ConnectError, stream.httpx.ReadError, stream.httpx.DecodingError])
def test_reconnection_limit(monkeypatch, error_type):
    setup(monkeypatch)
    monkeypatch.setattr(stream.api, "get_agent_run", lambda *a: {"run_id": "r1", "status": "running"})
    calls = []
    @contextmanager
    def connect(*a, **kw):
        calls.append(1)
        raise error_type("offline")
        yield
    monkeypatch.setattr(stream.httpx, "stream", connect)
    with pytest.raises(BackendClientError, match="기존 작업"):
        stream.receive_run(None, "guest", "r1")
    assert len(calls) == 3


@pytest.mark.parametrize("data", [None, [], {"run_id":"r1","status":[]},
    {"run_id":"r1","status":{}}, {"run_id":"r1","status":True}])
def test_malformed_snapshot_is_contract_error(data):
    with pytest.raises(BackendClientError) as caught:
        stream.final_result(data, "r1")
    assert caught.value.code == "CONTRACT_MISMATCH"


@pytest.mark.parametrize("patch", [{"step_id": []}, {"step_id": " "}, {"tool": []},
    {"stage": {}}, {"message": None}, {"status": []}, {"result_count": True},
    {"result_count": -1}, {"evidence_previews": None}, {"evidence_previews": [None]},
    {"evidence_previews": [{"title": []}]}])
def test_invalid_event_never_reaches_callback(monkeypatch, patch):
    setup(monkeypatch)
    monkeypatch.setattr(stream.api,"get_agent_run",lambda *args: {"run_id":"r1","status":"running"})
    data = {"run_id":"r1","step_id":"search", **patch}
    seen = []

    @contextmanager
    def connect(*args, **kwargs):
        class Response:
            headers = {"content-type":"text/event-stream"}
            def raise_for_status(self): pass
            def iter_lines(self):
                yield from ["id: 1", "event: step.completed", "data: "+json.dumps(data), ""]
        yield Response()

    monkeypatch.setattr(stream.httpx,"stream",connect)
    with pytest.raises(BackendClientError) as caught:
        stream.receive_run(None,"guest","r1",on_event=lambda *args: seen.append(args))
    assert caught.value.code == "CONTRACT_MISMATCH"
    assert seen == []


def test_normal_preview_event_accepts_nullable_count_and_extra_fields():
    stream.validate_event("step.completed", {"run_id":"r1","step_id":"search", "tool":"search_laws",
        "result_count":None,"future_field":{}, "evidence_previews":[{"evidence_id":"law:1",
        "title":"법령","content_preview":"본문","source_type":"law"}]},"r1")


def test_normal_validation_event_and_guest_storage_warning_are_accepted():
    from frontend.components.stream_analysis import friendly_event
    stream.validate_event("step.started", {"run_id":"r1","step_id":"validation", "tool":None,
        "stage":"validation", "result_count":None},"r1")
    stream.validate_event("guest.storage_failed", {"run_id":"r1","message":"temporary storage unavailable"},"r1")
    assert "분석은 계속" in friendly_event("guest.storage_failed", {})
