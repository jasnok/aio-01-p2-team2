"""Same-process retrieval cache comparison with a prewarmed embedding."""
import argparse
import json
import sys
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from legal_mcp.services.legal_search_service import LegalSearchService, _result_cache
from legal_mcp.providers.embedding_provider import create_embedding
from scripts.portfolio_smoke import SCENARIOS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    service = LegalSearchService()
    records = []
    for category, query in SCENARIOS[:3]:
        _result_cache.clear()
        create_embedding(query)
        times = []
        reference = None
        for repeat in range(4):
            started = perf_counter()
            result = service._hybrid_search(query, category, ["LAW", "CASE", "CONSULTATION"], 3)
            times.append(round((perf_counter()-started)*1000, 3))
            if reference is None:
                reference = result
            assert result == reference
        records.append({"category": category, "cold_result_cache_ms": times[0],
                        "warm_result_cache_ms": times[1:], "identical_evidence": True})
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"scope": "single cold retrieval + three warm retrievals, embedding prewarmed; not end-to-end latency or p95",
                                  "records": records}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(records, ensure_ascii=False))


if __name__ == "__main__":
    main()
