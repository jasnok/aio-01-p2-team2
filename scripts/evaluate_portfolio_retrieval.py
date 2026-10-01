"""Compare frozen baseline/current/RRF on the same DB and cached embeddings.

Run inside the MCP container (or with an explicit local DATABASE_URL).
One embedding request per unique question; no answer-generation calls.
"""

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.portfolio_dataset import build_dataset
from legal_mcp.services.legal_search_service import LegalSearchService
from legal_mcp.providers.embedding_provider import create_embedding
from legal_mcp.services import legal_search_service


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True, help="Frozen baseline service module")
    parser.add_argument("--baseline-repository", help="Frozen baseline SQL repository module")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("baseline_retrieval", args.baseline)
    baseline_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(baseline_module)
    baseline = baseline_module.LegalSearchService()
    if args.baseline_repository:
        repository_spec = importlib.util.spec_from_file_location("baseline_sql", args.baseline_repository)
        repository_module = importlib.util.module_from_spec(repository_spec)
        repository_spec.loader.exec_module(repository_module)
        baseline.repository = repository_module.LegalRepository()
    current = LegalSearchService()
    current.settings = current.settings.model_copy(update={"retrieval_cache_ttl_seconds": 0})
    rrf = LegalSearchService()
    rrf.settings = rrf.settings.model_copy(update={"retrieval_fusion": "rrf", "retrieval_cache_ttl_seconds": 0})
    records = []
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    for case in build_dataset():
        record = {**case, "variants": {}}
        # Use precisely the same embedding in all three variants. Timings below
        # are warm-cache retrieval timings, not end-to-end user latency.
        try:
            create_embedding(case["query"])
            for name, service in (("baseline", baseline), ("weighted", current), ("rrf", rrf)):
                started = perf_counter()
                rows = service._hybrid_search(case["query"], case["category"], ["LAW", "CASE", "CONSULTATION"], 3)
                ids = [row["document_id"] for row in rows]
                record["variants"][name] = {
                    "document_ids": ids,
                    "scores": [row["similarity"] for row in rows],
                    "titles": [row.get("title") or row.get("case_name") for row in rows],
                    "chunks": [row["chunk_content"] for row in rows],
                    "retrieval_ms": round((perf_counter() - started) * 1000),
                    "identifier_hit_at_3": bool(set(ids) & set(case["expected_document_ids"])) if case["kind"] == "identifier" else None,
                }
        except Exception as error:
            record["error"] = type(error).__name__
        records.append(record)
        destination.write_text(json.dumps({"scope": "identifier lookup + unlabelled natural questions; not legal accuracy",
                                          "records": records}, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(case["id"], "ERROR" if record.get("error") else "done", flush=True)
    summary = {}
    for name in ("baseline", "weighted", "rrf"):
        labelled = [r["variants"][name] for r in records if r["kind"] == "identifier" and name in r["variants"]]
        summary[name] = {"identifier_hits": sum(r["identifier_hit_at_3"] for r in labelled),
                         "identifier_count": len(labelled), "natural_quality": "pending_human_review"}
    destination.write_text(json.dumps({"scope": "identifier lookup + unlabelled natural questions; not legal accuracy",
                                      "config": {"embedding_model": current.settings.embedding_model,
                                                 "embedding_dimension": current.settings.embedding_dimension,
                                                 "filter_enabled": current.settings.retrieval_filter_enabled,
                                                 "vector_weight": current.settings.vector_weight,
                                                 "keyword_weight": current.settings.keyword_weight},
                                      "summary": summary, "records": records}, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary), flush=True)
    return int(any(record.get("error") for record in records))


if __name__ == "__main__":
    sys.exit(main())
