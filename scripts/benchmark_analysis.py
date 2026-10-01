"""Repeated live runs; raw samples are stored once, summaries reference files."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import math
import subprocess
import sys
from pathlib import Path


def latency(values):
    values = sorted(values)
    def quantile(p):
        return values[max(0, math.ceil(len(values)*p)-1)] if values else None
    return {"samples": len(values), "p50_ms": quantile(.5),
        "p95_ms": quantile(.95) if len(values) >= 20 else None,
        "p95_status": "reported_with_sample_count" if len(values) >= 20 else "insufficient_samples_minimum_20"}


def summarize(samples):
    successful = [row for row in samples if not row.get("error") and
        row.get("run", {}).get("status") in {"completed", "stopped"} and all(row.get("checks", {}).values())]
    statuses = Counter(row.get("run", {}).get("status", "error") for row in samples)
    finals = [(row.get("run", {}).get("result") or {}) for row in samples]
    diagnostics = [final.get("diagnostics", {}) for final in finals]
    return {"requests": len(samples), "successes": len(successful), "statuses": dict(statuses),
        "generation_statuses": dict(Counter(final.get("generation_status") or "missing" for final in finals)),
        **latency([row["elapsed_ms"] for row in successful]),
        "check_failures": sum(bool(row.get("checks")) and not all(row["checks"].values()) for row in samples),
        "unchecked_requests": sum(not row.get("checks") for row in samples),
        "fallbacks": sum(final.get("generation_status") == "fallback" for final in finals),
        "repairs": sum(d.get("repair_attempts", 0) > 0 for d in diagnostics),
        "repair_rate_all_requests": sum(d.get("repair_attempts", 0) > 0 for d in diagnostics)/len(samples) if samples else 0,
        "excluded_claims": sum(d.get("excluded_claims", 0) for d in diagnostics),
        "model_calls": sum(d.get("llm_calls", len(d.get("model_calls", []))) for d in diagnostics),
        "first_evidence": latency([row["live_sse"]["first_evidence_ms"] for row in successful
            if row.get("live_sse", {}).get("first_evidence_ms") is not None]),
        "completed_llm": latency([row["elapsed_ms"] for row in successful
            if (row.get("run", {}).get("result") or {}).get("generation_status") == "llm"])}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--output-dir", default="output/latency/live")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--cache-state", choices=["cold", "primed", "uncontrolled"], default="uncontrolled")
    args = parser.parse_args()
    if not 1 <= args.repeats <= 10:
        parser.error("repeats must be between 1 and 10 (4 API calls per repeat)")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip())
    folder = Path(args.output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    samples, files, failed = [], [], False
    for repeat in range(args.repeats):
        output = folder / f"run-{repeat+1}.json"
        output.unlink(missing_ok=True)
        process = subprocess.run([sys.executable, "-X", "utf8", "scripts/portfolio_smoke.py",
            "--base-url", args.base_url, "--cache-state", args.cache_state, "--output", str(output)], check=False)
        if not output.exists():
            raise RuntimeError("benchmark output missing")
        samples.extend(json.loads(output.read_text(encoding="utf-8")))
        files.append(output.name)
        failed |= process.returncode != 0
    result = {"created_at": datetime.now(timezone.utc).isoformat(), "git_commit": commit,
        "working_tree_dirty": dirty, "cache_control": args.cache_state,
        "dataset_version": "smoke-4-v1", "scope": "sequential requests; live SSE; no concurrent load claim",
        "summary": summarize(samples), "sample_files": files,
        "scenarios": {str(index): summarize([sample for position, sample in enumerate(samples)
            if sample.get("scenario_index", position % 4) == index]) for index in range(4)}}
    (folder / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["summary"]))
    return int(failed or result["summary"]["check_failures"] > 0 or result["summary"]["unchecked_requests"] > 0)


if __name__ == "__main__":
    sys.exit(main())
