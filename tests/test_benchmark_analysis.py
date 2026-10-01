from scripts.benchmark_analysis import summarize


def test_small_sample_does_not_report_p95_and_failures_stay_in_denominator():
    rows = [{"elapsed_ms": n, "run": {"status": "completed", "result": {"generation_status": "llm"}}}
            for n in (10, 20, 30)]
    rows.append({"elapsed_ms": 100, "run": {"status": "failed"}})
    result = summarize(rows)
    assert result["requests"] == 4 and result["successes"] == 3
    assert result["p50_ms"] == 20 and result["p95_ms"] is None


def test_failure_exit_preserves_raw_file_and_summary_reference(monkeypatch, tmp_path):
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
