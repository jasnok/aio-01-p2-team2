"""Repeated actual runs with explicit request count and version provenance."""
import argparse
import json
import math
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone


def summarize(samples):
    successful = [row for row in samples if row.get("run", {}).get("status") in {"completed", "stopped"}]
    values = sorted(row["elapsed_ms"] for row in successful)
    def quantile(p):
        return values[max(0, math.ceil(len(values)*p)-1)] if values else None
    return {"requests": len(samples), "successes": len(successful),
        "p50_ms": quantile(.5), "p95_ms": quantile(.95) if len(values) >= 20 else None,
        "p95_status": "reported" if len(values) >= 20 else "insufficient_samples_minimum_20",
        "fallbacks": sum((r.get("run", {}).get("result") or {}).get("generation_status") == "fallback" for r in samples)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--output-dir", default="output/phase3/benchmark")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--cache-state", choices=["cold", "warm", "uncontrolled"], default="uncontrolled")
    args = parser.parse_args()
    if not 1 <= args.repeats <= 10:
        parser.error("repeats must be between 1 and 10 (4 API calls per repeat)")
    folder = Path(args.output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    samples = []
    for repeat in range(args.repeats):
        output = folder / f"run-{repeat+1}.json"
        process = subprocess.run([sys.executable, "-X", "utf8", "scripts/portfolio_smoke.py",
            "--base-url", args.base_url, "--output", str(output)], check=False)
        if not output.exists():
            raise RuntimeError("benchmark output missing")
        samples.extend(json.loads(output.read_text(encoding="utf-8")))
        if process.returncode:
            print("Some checks failed; retained in report.", file=sys.stderr)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip())
    result = {"created_at": datetime.now(timezone.utc).isoformat(), "git_commit": commit,
        "working_tree_dirty": dirty, "cache_state_operator_declared": args.cache_state,
        "dataset_version": "smoke-4-v1", "scope": "sequential requests; not concurrent load benchmark",
        "summary": summarize(samples), "samples": samples}
    (folder / "summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["summary"]))


if __name__ == "__main__":
    main()
