"""Compare per-term and shared DB connections, without model requests."""
import argparse
import hashlib
import json
from pathlib import Path
from statistics import median
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from legal_mcp.repositories.legal_repository import LegalRepository
from legal_mcp.services.query_terms import extract_query_terms
from scripts.benchmark_provenance import capture, finish, database_profile

CODE_PATHS = ["scripts/benchmark_keyword_connections.py", "scripts/benchmark_provenance.py",
              "legal_mcp/repositories/legal_repository.py", "legal_mcp/services/query_terms.py",
              "legal_mcp/infrastructure/database.py"]
PACKAGES = ["psycopg", "pgvector"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    provenance = capture(CODE_PATHS, PACKAGES)
    provenance["database_before"] = database_profile()
    repo = LegalRepository()
    cases = [("보증금 임대차 계약갱신 내용증명", "housing"),
             ("퇴직금 임금 해고 근로계약", "labor"),
             ("환불 반품 배송 하자", "consumer")]
    reports = []
    for query, category in cases:
        terms = extract_query_terms(query)
        timings = {"per_term_connection": [], "shared_connection": []}
        hashes = set()
        for index in range(12):
            names = list(timings)
            if index % 2:
                names.reverse()
            pair = {}
            for name in names:
                start = perf_counter()
                if name == "per_term_connection":
                    rows = [row for term in terms for row in
                            repo.search_documents_by_keyword(term, category, ["LAW", "CASE", "CONSULTATION"], 9)]
                else:
                    rows = repo.search_documents_by_keywords(terms, category, ["LAW", "CASE", "CONSULTATION"], 9)
                elapsed = (perf_counter() - start) * 1000
                pair[name] = rows
                hashes.add(hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest())
                if index >= 2:
                    timings[name].append(elapsed)
            if pair[names[0]] != pair[names[1]]:
                raise RuntimeError("Paired keyword results differ")
        record = {"category": category, "query": query, "terms": terms,
                  "rows": len(rows), "result_hashes": sorted(hashes),
                  "equivalent_pairs": 12, "samples_ms": timings,
                  "median_ms": {name: median(values) for name, values in timings.items()}}
        reports.append(record)
        print(category, json.dumps(record["median_ms"]), flush=True)
    provenance["database_after"] = database_profile()
    provenance["database_counts_unchanged"] = provenance["database_before"] == provenance["database_after"]
    report = {"scope": "Keyword DB retrieval only; zero model requests; SQL unchanged",
              "python": sys.version.split()[0], "warmup_pairs": 2, "measured_pairs": 10,
              "cases": reports, "provenance": finish(provenance, CODE_PATHS, PACKAGES)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
