"""Structured operational logs without questions, answers or credentials."""
import json
import logging

logger = logging.getLogger("lawpath.metrics")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False


def log_result(run_id: str, result) -> None:
    logger.info(json.dumps({"event": "agent_run_metrics", "run_id": run_id,
                            "generation_status": result.generation_status,
                            "diagnostics": result.diagnostics}, ensure_ascii=False))
