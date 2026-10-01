import json
from scripts.portfolio_smoke import consume_sse
from scripts.benchmark_analysis import summarize


def test_live_sse_timing_excludes_replay_and_post_completion_checks():
    events = [("step.completed", {"evidence_previews": [{"title": "합성 근거"}]}),
              ("run.completed", {"status": "completed"})]
    lines = []
    for index, (name, payload) in enumerate(events, 1):
        lines.extend([f"id: {index}", f"event: {name}", "data: " + json.dumps(payload), ""])
    times = iter([1.25, 3.0])
    result = consume_sse(lines, started=1, clock=lambda: next(times))
    assert result["first_evidence_ms"] == 250
    assert result["terminal_ms"] == 2000 and result["stream_completed"]


def test_failed_contract_is_excluded_from_success_latency_but_counted():
    result = summarize([{"elapsed_ms": 100, "checks": {"citation_integrity": False},
        "run": {"status": "completed", "result": {"generation_status": "llm"}}}])
    assert result["requests"] == 1 and result["successes"] == 0
    assert result["check_failures"] == 1 and result["p50_ms"] is None
