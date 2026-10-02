"""Paired candidate retrieval with stored vectors; no embedding/model calls."""
import argparse
import hashlib
import json
from pathlib import Path
from statistics import median
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from legal_mcp.infrastructure.database import get_connection
from legal_mcp.repositories.legal_repository import LegalRepository
from legal_mcp.services.query_terms import extract_query_terms
from scripts.benchmark_provenance import capture, finish, database_profile

CODE_PATHS = ["scripts/benchmark_hybrid_connections.py", "scripts/benchmark_provenance.py",
              "legal_mcp/repositories/legal_repository.py", "legal_mcp/services/legal_search_service.py",
              "legal_mcp/services/query_terms.py", "legal_mcp/infrastructure/database.py"]
PACKAGES = ["psycopg", "pgvector"]


def separate(repo, embedding, terms, category, types):
    if types == ["LAW"]:
        vector = repo.search_laws(embedding, category, 9)
    elif types == ["CASE"]:
        vector = repo.search_cases(embedding, category, 9)
    else:
        vector = repo.search_legal_documents(embedding, category, types, 9)
    return vector, repo.search_documents_by_keywords(terms, category, types, 9)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Choose a new output path; existing evidence is preserved")
    provenance = capture(CODE_PATHS, PACKAGES)
    provenance["database_before"] = database_profile()
    repo, reports = LegalRepository(), []
    cases = [("보증금 임대차 계약", "housing", ["LAW"]),
             ("퇴직금 임금 해고", "labor", ["CASE"]),
             ("환불 반품 하자", "consumer", ["CONSULTATION"])]
    for query, category, types in cases:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""SELECT c.id, c.embedding FROM legal_chunks c
                    JOIN legal_documents d ON d.id=c.document_id
                    WHERE d.category=%s AND d.document_type=ANY(%s) AND c.embedding IS NOT NULL
                    ORDER BY c.id LIMIT 1""", (category, types))
                stored = cur.fetchone()
        if stored is None:
            raise ValueError("Stored vector missing")
        embedding = stored["embedding"].to_list()
        terms = extract_query_terms(query)
        timings = {"separate_connections": [], "shared_connection": []}
        hashes = set()
        for index in range(12):
            names = list(timings)
            if index % 2:
                names.reverse()
            pair = {}
            for name in names:
                started = perf_counter()
                rows = (separate(repo, embedding, terms, category, types) if name == "separate_connections"
                        else repo.search_hybrid_candidates(embedding, terms, category, types, 9))
                elapsed = (perf_counter() - started) * 1000
                pair[name] = rows
                hashes.add(hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest())
                if index >= 2:
                    timings[name].append(elapsed)
            if pair[names[0]] != pair[names[1]]:
                raise RuntimeError("Candidate results differ; inspect raw ordering before adopting")
        record = {"category": category, "document_types": types, "stored_chunk_id": stored["id"],
                  "embedding_sha256": hashlib.sha256(json.dumps(embedding).encode()).hexdigest(),
                  "keyword_count": len(terms), "connections_before": 2, "connections_after": 1,
                  "equivalent_pairs": 12, "result_hashes": sorted(hashes), "samples_ms": timings,
                  "median_ms": {name: median(values) for name, values in timings.items()}}
        reports.append(record)
        print(category, json.dumps(record["median_ms"]), flush=True)
    provenance["database_after"] = database_profile()
    provenance["database_counts_unchanged"] = provenance["database_before"] == provenance["database_after"]
    report = {"scope": "vector and keyword candidate DB retrieval; stored vectors; no API, embedding or model requests",
              "warmup_pairs": 2, "measured_pairs": 10, "cases": reports,
              "provenance": finish(provenance, CODE_PATHS, PACKAGES)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()

