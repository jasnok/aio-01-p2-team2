"""Operational metrics contain only explicitly allowed numeric fields."""
import json
import logging
import math

logger = logging.getLogger("lawpath.metrics")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False

NUMERIC_FIELDS = ("context_ms", "generation_ms", "intake_ms", "retrieval_ms",
                  "total_ms", "tool_calls", "evidence_count", "llm_calls",
                  "unknown_usage_calls", "excluded_claims")
GROUP_FIELDS = {
    "llm_usage_total": ("input_tokens", "output_tokens", "total_tokens"),
    "model_stage_ms": ("intake", "answer", "answer_repair", "verification", "term"),
    "tool_timings_ms": ("search_laws", "search_cases", "search_consultations", "search_legal_documents"),
}


def _numbers(source: dict, keys) -> dict:
    return {key: source[key] for key in keys if key in source
            and type(source[key]) in (int, float)
            and (type(source[key]) is int or math.isfinite(source[key]))
            and source[key] >= 0}


def log_result(run_id: str, result) -> None:
    source = result.diagnostics
    diagnostics = _numbers(source, NUMERIC_FIELDS)
    for name, keys in GROUP_FIELDS.items():
        if isinstance(source.get(name), dict):
            diagnostics[name] = _numbers(source[name], keys)
    status = result.generation_status
    if status not in {"llm", "fallback", "no_evidence", "clarification", "mock"}:
        status = "unknown"
    logger.info(json.dumps({"event": "agent_run_metrics", "run_id": run_id,
                            "generation_status": status,
                            "diagnostics": diagnostics}, ensure_ascii=False, allow_nan=False))
