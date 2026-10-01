"""Offline exact-offset context evaluation on frozen retrieval output."""
import argparse
import json
import sys
from pathlib import Path
from hashlib import sha256
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.services.text_spans import select_windows
from tests.portfolio_quality_dataset import quality_dataset


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="output/portfolio/retrieval-comparison.json")
    parser.add_argument("--output-dir", default="output/phase3")
    args = parser.parse_args()
    folder = Path(args.output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    source = Path(args.input).read_bytes()
    dataset = quality_dataset()
    (folder / "quality-dataset.json").write_text(json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = []
    for record in json.loads(source)["records"]:
        if record.get("error"):
            continue
        for variant_name, variant in record["variants"].items():
            for document_id, title, text in zip(variant["document_ids"], variant["titles"], variant["chunks"]):
                windows = select_windows(record["query"], text)
                rows.append({"query_id": record["id"], "query": record["query"], "variant": variant_name,
                    "document_id": document_id, "title": title, "source_text": text,
                    "windows": windows, "label_status": "pending_human_chunk_and_exception_review",
                    "exact_offsets": all(text[w["start"]:w["end"]] == w["quote"] for w in windows),
                    "source_characters": len(text), "selected_characters": sum(len(w["quote"]) for w in windows)})
    result = {"scope": "extractive integrity and size only; no semantic quality labels",
              "retrieval_sha256": sha256(source).hexdigest(), "records": rows,
              "summary": {"candidate_chunks": len(rows), "exact_offset_failures": sum(not r["exact_offsets"] for r in rows),
                          "empty_contexts": sum(not r["windows"] for r in rows),
                          "source_characters": sum(r["source_characters"] for r in rows),
                          "selected_characters": sum(r["selected_characters"] for r in rows)}}
    (folder / "context-review.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"dataset_count": len(dataset), **result["summary"]}))


if __name__ == "__main__":
    main()
