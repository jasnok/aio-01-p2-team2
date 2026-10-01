"""TTL-bound run snapshots shared by API workers. No durable job queue implied."""

import json
from datetime import datetime, timezone

from backend.app.core.config import get_settings
from backend.app.services.session_service import sessions, SessionStoreUnavailableError


def enabled() -> bool:
    settings = get_settings()
    return settings.redis_enabled and not settings.backend_mock_mode


async def save_snapshot(run: dict) -> None:
    if not enabled():
        return
    try:
        client = await sessions._redis_client()
        await client.set(f"lawpath:run:{run['run_id']}", json.dumps(run, ensure_ascii=False),
                         ex=get_settings().agent_run_ttl_seconds)
    except Exception as error:
        raise SessionStoreUnavailableError() from error


async def read_snapshot(run_id: str) -> dict | None:
    if not enabled():
        return None
    try:
        client = await sessions._redis_client()
        raw = await client.get(f"lawpath:run:{run_id}")
        run = json.loads(raw) if raw else None
        if run and run["status"] in {"queued", "running"}:
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(run["created_at"])).total_seconds()
            if age > get_settings().agent_run_timeout_seconds + 10:
                # A killed API process cannot resume asyncio tasks. Report an
                # interrupted run instead of leaving polling clients stuck.
                run["status"] = "failed"
                run["error"] = {"code": "ANALYSIS_INTERRUPTED", "message": "분석 실행이 중단됐습니다. 새로 요청해 주세요."}
                run["events"].append({"id": len(run["events"]) + 1, "event": "run.failed", "data": {
                    "run_id": run_id, "status": "failed", "message": run["error"]["message"]}})
                await save_snapshot(run)
        return run
    except Exception as error:
        raise SessionStoreUnavailableError() from error


async def reserve_run(run: dict, fingerprint: list, idempotency_key: str) -> tuple[dict, bool]:
    """Atomically reserve the key and snapshot so a second worker cannot launch it."""
    import hashlib
    key_hash = hashlib.sha256(json.dumps([run["owner_id"], idempotency_key]).encode()).hexdigest()
    key = f"lawpath:run-idempotency:{key_hash}"
    payload = json.dumps({"run_id": run["run_id"], "fingerprint": fingerprint}, ensure_ascii=False)
    script = """
        local old = redis.call('GET', KEYS[1])
        if old then return old end
        redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[3])
        redis.call('SET', KEYS[2], ARGV[2], 'EX', ARGV[3])
        return ''
    """
    try:
        client = await sessions._redis_client()
        old = await client.eval(script, 2, key, f"lawpath:run:{run['run_id']}",
                                payload, json.dumps(run, ensure_ascii=False),
                                get_settings().agent_run_ttl_seconds)
        if not old:
            return run, True
        reservation = json.loads(old)
        if reservation["fingerprint"] != fingerprint:
            raise ValueError("IDEMPOTENCY_CONFLICT")
        existing = await read_snapshot(reservation["run_id"])
        if existing is None:
            raise SessionStoreUnavailableError()
        return existing, False
    except ValueError:
        raise
    except Exception as error:
        raise SessionStoreUnavailableError() from error
