"""Real Redis atomic reservation check; synthetic records expire via normal TTL."""
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.services.agent_run_store import reserve_run, read_snapshot, save_snapshot
from backend.app.services.session_service import sessions


async def main():
    owner = f"persistence-check-{uuid4()}"
    def run():
        return {"run_id": f"run-{uuid4()}", "owner_id": owner, "status": "queued", "events": [],
                "created_at": datetime.now(timezone.utc).isoformat(), "result": None}
    first, second = await asyncio.gather(reserve_run(run(), ["housing", "synthetic", False, None], "same-key"),
                                        reserve_run(run(), ["housing", "synthetic", False, None], "same-key"))
    checks = {"single_reservation": sum(created for _, created in (first, second)) == 1,
              "same_run": first[0]["run_id"] == second[0]["run_id"]}
    reserved = first[0]
    reserved.update({"status": "completed", "result": {"synthetic": True}})
    await save_snapshot(reserved)
    checks["restored_snapshot"] = await read_snapshot(reserved["run_id"]) == reserved
    client = await sessions._redis_client()
    ttl = await client.ttl(f"lawpath:run:{reserved['run_id']}")
    checks["ttl"] = 0 < ttl <= 86400
    try:
        await reserve_run(run(), ["labor", "different", False, None], "same-key")
        checks["conflict"] = False
    except ValueError:
        checks["conflict"] = True
    print(json.dumps(checks), flush=True)
    return int(not all(checks.values()))


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
