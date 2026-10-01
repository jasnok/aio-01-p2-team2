"""Create blind review forms from synthetic latency experiments; no invented scores."""
import argparse
from hashlib import sha256
import json
from pathlib import Path


def create_review(folder):
    index = json.loads((folder/"index.json").read_text(encoding="utf-8"))
    rows, private = [], []
    for row in index["runs"]:
        sample = json.loads((folder/row["file"]).read_text(encoding="utf-8"))
        identifier = sha256(row["file"].encode()).hexdigest()[:12]
        rows.append({"review_id": identifier, "question": sample["question"],
            "scope": sample.get("scope", "pipeline"), "intake": sample.get("intake"),
            "answer": sample.get("answer"), "reviewer": None, "scores": {
                "input_decision_correct": None, "question_answered": None,
                "all_claims_supported": None, "conditions_and_exceptions_preserved": None,
                "abstention_appropriate": None}, "notes": None})
        private.append({"review_id": identifier, "file": row["file"], "variant": row["variant"]})
    rows.sort(key=lambda row: row["review_id"])
    (folder/"quality-review.json").write_text(json.dumps({"status": "pending_human_review",
        "source_reference": {"file": index["input"], "sha256": index["input_sha256"]},
        "scoring": "true/false with justification; compare each claim with exact source quotes; do not use model verdict as label",
        "cases": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    (folder/"quality-review-key.json").write_text(json.dumps(private, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()
    print(create_review(args.folder))


if __name__ == "__main__":
    main()
