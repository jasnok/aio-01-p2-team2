"""Paired SQL timings on the same snapshot; not whole-app latency or accuracy."""
import argparse
import importlib.util
import json
import sys
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from legal_mcp.repositories.legal_repository import LegalRepository


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("baseline_repository", args.baseline)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    records = []
    for query, category in (("주택임대차보호법", "housing"), ("퇴직금", "labor"), ("환불", "consumer")):
        record = {"query": query, "category": category}
        for name, repository in (("baseline", module.LegalRepository()), ("current", LegalRepository())):
            started = perf_counter()
            rows = repository.search_documents_by_keyword(query, category, ["LAW", "CASE", "CONSULTATION"], 9)
            record[name] = {"elapsed_ms": round((perf_counter() - started) * 1000),
                            "document_ids": [r["document_id"] for r in rows],
                            "scores": [float(r["keyword_score"]) for r in rows],
                            "chunks": [r["chunk_content"] for r in rows]}
        record["equivalent_results"] = all(record["baseline"][key] == record["current"][key]
                                            for key in ("document_ids", "scores", "chunks"))
        records.append(record)
        Path(args.output).write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        print(query, record["baseline"]["elapsed_ms"], record["current"]["elapsed_ms"], record["equivalent_results"], flush=True)
    return int(not all(r["equivalent_results"] for r in records))


if __name__ == "__main__":
    sys.exit(main())
