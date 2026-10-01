"""Per-request call metadata without storing prompts or sensitive text."""
from contextvars import ContextVar
from contextlib import contextmanager
import asyncio
from time import perf_counter

calls = ContextVar("model_calls", default=None)


@contextmanager
def collect_calls():
    sink = []
    token = calls.set(sink)
    try:
        yield sink
    finally:
        calls.reset(token)


async def structured_call(provider, stage, prompt, message, schema, timeout=None):
    """Real providers use native async; sync test/CLI adapters remain compatible."""
    started = perf_counter()
    try:
        async with asyncio.timeout(timeout):
            method = getattr(provider, "generate_structured_async", None)
            result = await method(prompt, message, schema) if method else await asyncio.to_thread(
                provider.generate_structured, prompt, message, schema)
        record_call(stage, result)
        return result
    except BaseException as error:
        sink = calls.get()
        if sink is not None:
            sink.append({"stage": stage, "model": getattr(provider, "model_override", None),
                         "elapsed_ms": round((perf_counter()-started)*1000), "usage": {},
                         "status": "cancelled" if isinstance(error, asyncio.CancelledError) else "failed",
                         "error_type": type(error).__name__, "usage_known": False})
        raise


def record_call(stage, result):
    sink = calls.get()
    if sink is not None:
        sink.append({"stage": stage, "model": getattr(result, "model", None),
                     "elapsed_ms": getattr(result, "elapsed_ms", None),
                     "usage": getattr(result, "usage", None) or {},
                     "status": "completed", "usage_known": bool(getattr(result, "usage", None))})


def stage_provider(settings, stage, default_provider):
    model = getattr(settings, f"{stage}_model", None)
    effort = getattr(settings, f"{stage}_reasoning_effort", None)
    if (model or effort) and settings.llm_provider == "openai":
        from backend.app.providers.openai import OpenAIProvider
        return OpenAIProvider(model, reasoning_effort=effort)
    return default_provider
