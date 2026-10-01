"""Describe paired synthetic scenarios without claiming statistical quality."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", default="output/portfolio/after-smoke.json")
    parser.add_argument("--after", default="output/optimization/after-smoke.json")
    parser.add_argument("--output", default="output/optimization/comparison.json")
    args = parser.parse_args()
    before, after = [json.loads(Path(path).read_text(encoding="utf-8")) for path in (args.before, args.after)]
    rows = []
    for old, new in zip(before, after, strict=True):
        if old["question"] != new["question"]:
            raise ValueError("비교 질문이 다릅니다.")
        old_result, new_result = old.get("run", {}).get("result") or {}, new.get("run", {}).get("result") or {}
        rows.append({"category": new["category"], "before_status": old_result.get("generation_status"),
            "after_status": new_result.get("generation_status"),
            "before_elapsed_ms": old["elapsed_ms"], "after_elapsed_ms": new["elapsed_ms"],
            "before_diagnostics": old_result.get("diagnostics", {}), "after_diagnostics": new_result.get("diagnostics", {}),
            "after_checks": new.get("checks", {})})
    result = {"scope": "one run per synthetic question; changing model outputs, warm-cache state and service load are not controlled; not legal accuracy or p95",
        "human_relevance_status": "pending_human_review", "records": rows}
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps([{key: row[key] for key in ("category", "before_status", "after_status", "before_elapsed_ms", "after_elapsed_ms")} for row in rows], ensure_ascii=False))


if __name__ == "__main__":
    main()
