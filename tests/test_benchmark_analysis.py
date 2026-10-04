import pytest
from scripts.benchmark_analysis import summarize


CHECKS = dict.fromkeys(("idempotency", "real_mode", "live_sse_terminal", "terminal_status",
                       "owner_isolation", "sse_replay", "live_sse_sequence", "citation_integrity"), True)


def test_small_sample_does_not_report_p95_and_failures_stay_in_denominator():
    rows = [{"elapsed_ms": n, "checks": CHECKS, "run": {"status": "completed", "result": {"generation_status": "llm"}}}
            for n in (10, 20, 30)]
    rows.append({"elapsed_ms": 100, "run": {"status": "failed"}})
    result = summarize(rows)
    assert result["requests"] == 4 and result["successes"] == 3
    assert result["p50_ms"] == 20 and result["p95_ms"] is None


def test_failure_exit_preserves_raw_file_and_summary_reference(monkeypatch, tmp_path):
    tmp_path = tmp_path / "new-measurement"
    import json
    import sys
    from types import SimpleNamespace
    from scripts import benchmark_analysis as script
    def child(args, **kwargs):
        output = args[args.index("--output")+1]
        from pathlib import Path
        Path(output).write_text(json.dumps([{"elapsed_ms": 10,
            "checks": {"citation_integrity": False}, "run": {"status": "completed"}}]), encoding="utf-8")
        return SimpleNamespace(returncode=1)
    monkeypatch.setattr(script.subprocess, "run", child)
    monkeypatch.setattr(script.subprocess, "check_output", lambda args, **kwargs: "" if "--porcelain" in args else "test-commit")
    monkeypatch.setattr(sys, "argv", ["benchmark", "--output-dir", str(tmp_path)])
    assert script.main() == 1
    summary = json.loads((tmp_path/"summary.json").read_text(encoding="utf-8"))
    assert summary["sample_files"] == ["run-1.json"] and "samples" not in summary
    assert summary["summary"]["check_failures"] == 1


@pytest.mark.parametrize("checks", [None, {}, {"real_mode": True}, {**CHECKS, "real_mode": "true"},
                                   {**CHECKS, "real_mode": 1}, {**CHECKS, "real_mode": None}, []])
def test_unverified_or_malformed_checks_never_enter_success_latency(checks):
    row = {"elapsed_ms": 1, "checks": checks, "run": {"status": "completed"}}
    good = {"elapsed_ms": 100, "checks": CHECKS, "run": {"status": "completed"}}
    summary = summarize([row, good])
    assert summary["requests"] == 2 and summary["successes"] == 1
    assert summary["p50_ms"] == 100


@pytest.mark.parametrize("duration", [None, True, -1, float("nan"), float("inf"), "10"])
def test_invalid_duration_is_preserved_in_denominator_without_percentile(duration):
    result = summarize([{"elapsed_ms": duration, "checks": CHECKS, "run": {"status": "completed"}}])
    assert result["requests"] == 1 and result["successes"] == 0
    assert result["invalid_latency_requests"] == 1
    assert result["p50_ms"] is None


def test_generation_specific_checks_and_clarification_remain_distinct():
    base = {k: v for k, v in CHECKS.items() if k != "citation_integrity"}
    rows = [
        {"elapsed_ms": 10, "checks": base, "run": {"status": "stopped", "result": {"generation_status": "clarification"}}},
        {"elapsed_ms": 1, "checks": base, "run": {"status": "completed", "result": {"generation_status": "llm"}}},
        {"elapsed_ms": 2, "checks": CHECKS, "run": {"status": "completed", "result": {
            "generation_status": "llm", "diagnostics": {"citation_mode": "spans"}}}},
    ]
    result = summarize(rows)
    assert result["requests"] == 3 and result["successes"] == 1
    assert result["incomplete_check_requests"] == 2
    assert result["p50_ms"] == 10
    assert result["completed_llm"]["samples"] == 0


@pytest.mark.parametrize("first", [-1, 101, float("nan"), True, "10"])
def test_invalid_first_evidence_time_excludes_measurement(first):
    result = summarize([{"elapsed_ms": 100, "checks": CHECKS, "run": {"status": "completed"},
                         "live_sse": {"first_evidence_ms": first}}])
    assert result["successes"] == 0 and result["invalid_latency_requests"] == 1


@pytest.mark.parametrize("changes", [{"checks": {}}, {"checks": {"real_mode": True}},
                                     {"checks": {**CHECKS, "real_mode": 1}},
                                     {"elapsed_ms": -1}, {"run": {"status": "failed"}}, None, {}])
def test_cli_classifies_output_even_when_child_exits_zero(monkeypatch, tmp_path, changes):
    tmp_path = tmp_path / "new-measurement"
    import json
    import sys
    from pathlib import Path
    from types import SimpleNamespace
    from scripts import benchmark_analysis as script
    rows = [] if changes is None else [{"elapsed_ms": 100, "checks": CHECKS,
                                        "run": {"status": "completed"}, **changes}]
    def child(args, **kwargs):
        Path(args[args.index("--output") + 1]).write_text(json.dumps(rows), encoding="utf-8")
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(script.subprocess, "run", child)
    monkeypatch.setattr(script.subprocess, "check_output", lambda args, **kwargs: "" if "--porcelain" in args else "test-commit")
    monkeypatch.setattr(sys, "argv", ["benchmark", "--output-dir", str(tmp_path)])
    assert script.main() == (0 if changes == {} else 1)
    assert json.loads((tmp_path / "run-1.json").read_text(encoding="utf-8")) == rows
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert summary["summary"]["successes"] == (1 if changes == {} else 0)
    assert summary["sample_files"] == ["run-1.json"]
