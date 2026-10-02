"""Generate a numeric allowlist from existing measurements. No API calls."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from statistics import median
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from frontend.core.portfolio_evidence import DEFAULT_PATH, PortfolioEvidence


def build(directory):
    sources = []

    def read(name):
        raw = (directory / name).read_bytes()
        parsed = json.loads(raw)
        canonical = json.dumps(parsed, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        sources.append({"file": name, "sha256": hashlib.sha256(canonical).hexdigest()})
        return parsed

    def measured(values, expected, published):
        if len(values) != expected or not values or any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in values):
            raise ValueError("Invalid measurement samples")
        result = median(values)
        if not math.isclose(result, published, rel_tol=1e-9, abs_tol=1e-9):
            raise ValueError("Published median differs from samples")
        return result

    embedding = read("embedding-client-acquisition.json")
    row = {"experiment": "embedding", "samples": embedding["samples"],
           "warmup": embedding["warmup"], "python": embedding["python"]}
    for field, name in [("before_ms", "new_client"), ("after_ms", "reused_client")]:
        sample = embedding["results"][name]
        row[field] = measured(sample["samples_ms"], embedding["samples"], sample["median_ms"])
    rows = [row]
    keyword = read("keyword-connections.json")
    for case in keyword["cases"]:
        if len(case["result_hashes"]) != 1 or case["equivalent_pairs"] != keyword["warmup_pairs"] + keyword["measured_pairs"]:
            raise ValueError("Keyword result equivalence is not established")
        row = {"experiment": "keyword", "category": case["category"], "python": keyword["python"],
               "samples": keyword["measured_pairs"], "warmup": keyword["warmup_pairs"],
               "equivalent_pairs": case["equivalent_pairs"]}
        for field, name in [("before_ms", "per_term_connection"), ("after_ms", "shared_connection")]:
            row[field] = measured(case["samples_ms"][name], keyword["measured_pairs"], case["median_ms"][name])
        rows.append(row)
    environments = []
    for name in ("environment-windows.json", "environment-windows-clean.json", "environment-linux.json"):
        report = read(name)
        environments.append({"platform": report["platform"], "python": report["python"],
            "packages": len(report["packages"]), "errors": len(report["errors"]),
            "constraints_sha256": report["constraints_sha256"]})
    return PortfolioEvidence(rows=rows, sources=sources, environments=environments)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    payload = build(ROOT / "output" / "portfolio").model_dump_json(indent=2) + "\n"
    if args.check:
        if DEFAULT_PATH.read_text(encoding="utf-8") != payload:
            raise SystemExit("Portfolio evidence is stale; regenerate it")
    else:
        DEFAULT_PATH.write_text(payload, encoding="utf-8")
    print("Portfolio numeric evidence verified" if args.check else "Portfolio numeric evidence generated")


if __name__ == "__main__":
    main()
