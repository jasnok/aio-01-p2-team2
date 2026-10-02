"""Measure SDK construction/reuse only. Never calls an embedding API."""
import argparse
import json
from pathlib import Path
from statistics import median
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from legal_mcp.providers.embedding_provider import EmbeddingClients, OpenAIEmbeddingProvider


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # Explicit constructor key; no real credentials or requests are needed.
    key = "synthetic-no-network-key"
    pool = EmbeddingClients()
    results = {}
    try:
        for name in ("new_client", "reused_client"):
            samples = []
            for index in range(20):
                start = perf_counter()
                if name == "new_client":
                    provider = OpenAIEmbeddingProvider(api_key=key)
                    elapsed = (perf_counter() - start) * 1000
                    provider.close()
                else:
                    with pool.acquire(("benchmark",), "text-embedding-3-small", 1536, key):
                        elapsed = (perf_counter() - start) * 1000
                if index >= 5:
                    samples.append(elapsed)
            results[name] = {"samples_ms": samples, "median_ms": median(samples)}
    finally:
        pool.close()
    report = {"scope": "SDK acquisition only; zero API requests; excludes close time",
              "python": sys.version.split()[0], "platform": sys.platform,
              "warmup": 5, "samples": 15, "results": results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({name: result["median_ms"] for name, result in results.items()}))


if __name__ == "__main__":
    main()
