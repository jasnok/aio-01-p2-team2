"""Per-request call metadata without storing prompts or sensitive text."""
from contextvars import ContextVar

calls = ContextVar("model_calls", default=None)


def record_call(stage, result):
    sink = calls.get()
    if sink is not None:
        sink.append({"stage": stage, "model": getattr(result, "model", None),
                     "elapsed_ms": getattr(result, "elapsed_ms", None),
                     "usage": getattr(result, "usage", None) or {}})


def stage_provider(settings, stage, default_provider):
    model = getattr(settings, f"{stage}_model", None)
    if model and settings.llm_provider == "openai":
        from backend.app.providers.openai import OpenAIProvider
        return OpenAIProvider(model)
    return default_provider
