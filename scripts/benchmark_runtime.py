"""Paired warm-cache actual MCP retrieval; no answer/intake LLM calls."""
import argparse
import asyncio
import importlib.util
import json
import statistics
import sys
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.agents.models import AgentState
from backend.app.agents.registry import get_agent_profile
from backend.app.agents.runtime import LegalAgentRuntime
from scripts.portfolio_smoke import SCENARIOS


async def benchmark(args):
    spec = importlib.util.spec_from_file_location("baseline_runtime", args.baseline)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    runtimes = {"sequential": module.LegalAgentRuntime(), "parallel": LegalAgentRuntime()}
    records = []
    for category, question in SCENARIOS[:3]:
        profile = get_agent_profile(category)
        # Warm exactly the same queries before both measured variants.
        await runtimes["sequential"].run(profile, AgentState(request_id="warm", agent_id=category, question=question))
        results = {name: [] for name in runtimes}
        reference = None
        for repeat in range(args.repeats):
            order = list(runtimes) if repeat % 2 == 0 else list(reversed(runtimes))
            for name in order:
                started = perf_counter()
                _, evidence = await runtimes[name].run(profile,
                    AgentState(request_id="benchmark", agent_id=category, question=question))
                elapsed = round((perf_counter()-started)*1000)
                if reference is None:
                    reference = evidence
                if reference != evidence:
                    raise AssertionError("병렬 검색 결과가 순차 검색과 다릅니다.")
                results[name].append(elapsed)
        records.append({"category": category, "samples_ms": results,
            "median_ms": {name: statistics.median(samples) for name, samples in results.items()},
            "identical_evidence": True})
        print(category, records[-1]["median_ms"], flush=True)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"scope": "paired warm process-local retrieval cache, same MCP service; not end-to-end latency or p95",
        "repeats": args.repeats, "records": records}, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    asyncio.run(benchmark(args))
