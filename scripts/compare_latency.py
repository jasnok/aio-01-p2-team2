"""Bounded one-variable comparisons using fixed synthetic retrieval evidence."""
import argparse
import asyncio
from contextlib import contextmanager
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from time import perf_counter
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.core.config import get_settings
from backend.app.agents.intake_agent import IntakeAgent
from backend.app.schemas.legal import Evidence
from backend.app.services.legal_question_service import _generate_answer
from backend.app.services.model_metrics import collect_calls
from backend.app.providers.openai import close_async_clients

VARIANTS = {
    "baseline": {}, "repair0": {"answer_repair_attempts": 0},
    "intake_low": {"intake_reasoning_effort": "low"},
    "verification_low": {"verification_reasoning_effort": "low"},
    "answer_low": {"answer_reasoning_effort": "low"},
    "intake_candidate": {}, "verification_candidate": {},
    "context4": {"context_max_documents": 4},
    "compact_review": {"compact_verification_context": True},
}
CONTROLLED = {"semantic_verification_enabled": True, "answer_repair_attempts": 1,
    "intake_reasoning_effort": "", "answer_reasoning_effort": "", "verification_reasoning_effort": "",
    "context_max_documents": 6, "context_max_windows": 3, "context_document_budget": 2400,
    "compact_verification_context": False, "input_assessment_timeout_seconds": 60,
    "request_timeout_seconds": 60, "llm_provider": "openai", "citation_mode": "spans"}


@contextmanager
def experiment_settings(options):
    old = {key.upper(): os.environ.get(key.upper()) for key in options}
    try:
        for key, value in options.items():
            os.environ[key.upper()] = str(value)
        get_settings.cache_clear()
        yield get_settings()
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


async def run_case(case, variant, options, scope):
    started = perf_counter()
    result = {"category": case["category"], "variant": variant, "scope": scope,
              "question": case["question"], "settings": options, "human_review": "pending"}
    evidence = [Evidence.model_validate(item) for item in case["evidence"]]
    with experiment_settings(options) as settings, collect_calls() as records:
        result["effective_settings"] = {key: getattr(settings, key) for key in options}
        try:
            async with asyncio.timeout(150):
                ready = True
                if scope != "answer":
                    intake = await IntakeAgent().assess(case["category"], case["question"])
                    result["intake"] = intake.model_dump()
                    ready = intake.is_ready_for_search
                if ready and scope != "intake":
                    outcome = await _generate_answer(case["category"], case["question"], evidence, [])
                    result.update({"answer": outcome.draft.model_dump(), "llm_used": outcome.llm_used,
                                   "diagnostics": outcome.diagnostics,
                                   "generation_status": "llm" if outcome.llm_used else "fallback"})
                else:
                    result["llm_used"] = False
                    result["generation_status"] = "intake_only" if scope == "intake" else "clarification"
            result["status"] = "completed"
        except Exception as error:
            result.update({"status": "failed", "error_type": type(error).__name__})
        result["model_calls"] = records
    result["elapsed_ms"] = round((perf_counter()-started)*1000)
    result["known_tokens"] = sum(row["usage"].get("total_tokens", 0) for row in records)
    return result


async def compare(args):
    folder = Path(args.output_dir)
    folder.mkdir(parents=True, exist_ok=False)
    source = Path(args.input)
    samples = json.loads(source.read_text(encoding="utf-8"))
    cases = []
    for index in args.scenarios:
        sample = samples[index]
        final = sample["run"]["result"]
        cases.append({"category": sample["category"], "question": sample["question"],
            "evidence": final["related_laws"] + final["similar_cases"] + final["consultations"]})
    base_model = get_settings().openai_model
    options = {name: {**CONTROLLED, "intake_model": base_model, "answer_model": base_model,
                     "verification_model": base_model, **VARIANTS[name]} for name in args.variants}
    if "intake_candidate" in options:
        options["intake_candidate"]["intake_model"] = args.candidate_model
    if "verification_candidate" in options:
        options["verification_candidate"]["verification_model"] = args.candidate_model
    index = {"input": str(source), "input_sha256": sha256(source.read_bytes()).hexdigest(),
        "scope": args.scope + "; fixed synthetic evidence; no live retrieval/cache latency",
        "human_quality_review": "pending", "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "working_tree_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()),
        "max_logical_calls": args.max_calls, "network_retries_scope": "SDK allows one retry per logical call",
        "runs": []}
    try:
        for repeat in range(args.repeats):
            for case_id, case in enumerate(cases):
                order = args.variants if (repeat+case_id) % 2 == 0 else list(reversed(args.variants))
                for name in order:
                    result = await run_case(case, name, options[name], args.scope)
                    filename = f"case-{args.scenarios[case_id]}-{name}-{repeat+1}.json"
                    (folder/filename).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                    row = {"file": filename, "scenario": args.scenarios[case_id], "variant": name,
                        "elapsed_ms": result["elapsed_ms"], "known_tokens": result["known_tokens"],
                        "status": result["status"], "llm_used": result.get("llm_used", False),
                        "generation_status": result.get("generation_status"),
                        "claims": len(result.get("answer", {}).get("claims", [])),
                        "calls": len(result["model_calls"])}
                    index["runs"].append(row)
                    (folder/"index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
                    print(json.dumps(row, ensure_ascii=False), flush=True)
    finally:
        await close_async_clients()
    return int(any(row["status"] == "failed" for row in index["runs"]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="output/phase3/benchmark/run-1.json")
    parser.add_argument("--output-dir", default="output/latency/comparison")
    parser.add_argument("--variants", nargs="+", choices=list(VARIANTS), default=["baseline", "repair0"])
    parser.add_argument("--scenarios", nargs="+", type=int, choices=[0, 1, 2], default=[0, 2])
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--scope", choices=["answer", "intake", "pipeline"], default="answer")
    parser.add_argument("--candidate-model", default="gpt-5-nano")
    parser.add_argument("--max-calls", type=int, default=36)
    args = parser.parse_args()
    maximum = len(args.scenarios)*len(args.variants)*args.repeats*{"answer": 4, "intake": 2, "pipeline": 6}[args.scope]
    if not 1 <= args.repeats <= 5 or maximum > args.max_calls or args.max_calls > 120:
        parser.error("estimated logical calls exceed budget; max-calls must be <=120, repeats 1..5")
    if len(set(args.variants)) != len(args.variants):
        parser.error("variants must be unique")
    if len(set(args.scenarios)) != len(args.scenarios):
        parser.error("scenarios must be unique")
    if args.scope == "answer" and any(name.startswith("intake_") for name in args.variants):
        parser.error("intake variants require --scope intake or pipeline")
    if args.scope == "intake" and any(name not in {"baseline", "intake_low", "intake_candidate"} for name in args.variants):
        parser.error("intake scope requires intake variants")
    try:
        return asyncio.run(compare(args))
    except FileExistsError:
        parser.error("output directory already exists; choose a new experiment directory")


if __name__ == "__main__":
    sys.exit(main())
