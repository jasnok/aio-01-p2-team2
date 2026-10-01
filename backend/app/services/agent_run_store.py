"""TTL-bound run snapshots shared by API workers. No durable job queue implied."""

import json
from datetime import datetime, timezone

from backend.app.core.config import get_settings
from backend.app.services.session_service import sessions, SessionStoreUnavailableError


class SnapshotConflictError(RuntimeError):
    """A stale or invalid writer must stop; current is internal, never public."""

    def __init__(self, current: dict | None, reason: str):
        super().__init__("Run snapshot write rejected")
        self.current = current
        self.reason = reason


_SAVE_SNAPSHOT = """
    local raw = redis.call('GET', KEYS[1])
    if not raw then return {0, '', 'expired'} end
    local old = cjson.decode(raw)
    local new = cjson.decode(ARGV[1])
    local function reject(reason) return {0, raw, reason} end
    local function equal(a, b)
        if type(a) ~= type(b) then return false end
        if type(a) ~= 'table' then return a == b end
        for k, v in pairs(a) do if not equal(v, b[k]) then return false end end
        for k, v in pairs(b) do if a[k] == nil then return false end end
        return true
    end
    if (old.revision or 0) ~= tonumber(ARGV[3]) then return reject('revision') end
    for _, field in ipairs({'run_id', 'owner_id', 'actor', 'category', 'question',
                            'save_selected', 'conversation_id', 'created_at'}) do
        if not equal(old[field], new[field]) then return reject('identity') end
    end
    if old.status == 'completed' or old.status == 'stopped' or old.status == 'failed' then
        new.revision = old.revision
        if equal(old, new) then return {1, raw, 'unchanged'} end
        return reject('terminal')
    end
    local allowed = {queued={queued=true, running=true, failed=true},
                     running={running=true, completed=true, stopped=true, failed=true}}
    if not allowed[old.status] or not allowed[old.status][new.status] then
        return reject('transition')
    end
    local events = new.events or {}
    if #events < #(old.events or {}) then return reject('events') end
    for i, event in ipairs(old.events or {}) do
        if not equal(event, events[i]) then return reject('events') end
    end
    for i, event in ipairs(events) do
        if event.id ~= i then return reject('events') end
    end
    if (new.status == 'completed' or new.status == 'stopped') and
       (new.result == nil or new.result == cjson.null) then return reject('result') end
    if new.status == 'failed' and (new.error == nil or new.error == cjson.null) then
        return reject('error')
    end
    -- Keep Python's JSON representation: cjson encodes empty arrays as objects.
    local updated = ARGV[1]
    redis.call('SET', KEYS[1], updated, 'EX', ARGV[2])
    return {1, updated, 'saved'}
"""


# Compare the exact snapshot read by the poller inside Redis, where a worker's
# completion cannot interleave between the comparison and the write.
_INTERRUPT_SNAPSHOT = """
    local current = redis.call('GET', KEYS[1])
    if not current then return '' end
    if current ~= ARGV[1] then return current end
    redis.call('SET', KEYS[1], ARGV[2], 'KEEPTTL')
    return ARGV[2]
"""


def enabled() -> bool:
    settings = get_settings()
    return settings.redis_enabled and not settings.backend_mock_mode


async def save_snapshot(run: dict) -> None:
    if not enabled():
        return
    try:
        client = await sessions._redis_client()
        expected_revision = run.get("revision", 0)
        candidate = dict(run, revision=expected_revision + 1)
        accepted, raw, reason = await client.eval(
            _SAVE_SNAPSHOT, 1, f"lawpath:run:{run['run_id']}",
            json.dumps(candidate, ensure_ascii=False), get_settings().agent_run_ttl_seconds,
            expected_revision)
        current = json.loads(raw) if raw else None
        if not accepted:
            raise SnapshotConflictError(current, reason)
        run["revision"] = current.get("revision", 0)
    except SnapshotConflictError:
        raise
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
                run["revision"] = run.get("revision", 0) + 1
                run["updated_at"] = datetime.now(timezone.utc).isoformat()
                run["error"] = {"code": "ANALYSIS_INTERRUPTED", "message": "분석 실행이 중단됐습니다. 새로 요청해 주세요."}
                run["events"].append({"id": len(run["events"]) + 1, "event": "run.failed", "data": {
                    "run_id": run_id, "status": "failed", "message": run["error"]["message"]}})
                current = await client.eval(
                    _INTERRUPT_SNAPSHOT, 1, f"lawpath:run:{run_id}",
                    raw, json.dumps(run, ensure_ascii=False))
                # Return the winner, including expiration, rather than a local
                # failure that may no longer describe the authoritative state.
                run = json.loads(current) if current else None
        return run
    except Exception as error:
        raise SessionStoreUnavailableError() from error


async def reserve_run(run: dict, fingerprint: list, idempotency_key: str) -> tuple[dict, bool]:
    """Atomically reserve the key and snapshot so a second worker cannot launch it."""
    import hashlib
    key_hash = hashlib.sha256(json.dumps([run["owner_id"], idempotency_key]).encode()).hexdigest()
    key = f"lawpath:run-idempotency:{key_hash}"
    payload = json.dumps({"run_id": run["run_id"], "fingerprint": fingerprint}, ensure_ascii=False)
    initial = dict(run, revision=1)
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
                                payload, json.dumps(initial, ensure_ascii=False),
                                get_settings().agent_run_ttl_seconds)
        if not old:
            run["revision"] = 1
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
