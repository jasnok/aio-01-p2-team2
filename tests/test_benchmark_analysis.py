from scripts.benchmark_analysis import summarize


def test_small_sample_does_not_report_p95_and_failures_stay_in_denominator():
    rows = [{"elapsed_ms": n, "run": {"status": "completed", "result": {"generation_status": "llm"}}}
            for n in (10, 20, 30)]
    rows.append({"elapsed_ms": 100, "run": {"status": "failed"}})
    result = summarize(rows)
    assert result["requests"] == 4 and result["successes"] == 3
    assert result["p50_ms"] == 20 and result["p95_ms"] is None
