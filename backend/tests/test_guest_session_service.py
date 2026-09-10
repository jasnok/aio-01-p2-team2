import asyncio

from backend.app.services import guest_session_service
from backend.app.services.guest_session_service import GuestSessionService


def memory_settings():
    return type("Settings", (), {"redis_enabled": False, "guest_session_ttl_seconds": 3600})()


def run(run_id: str) -> dict:
    return {
        "run_id": run_id,
        "category": "consumer",
        "question": "중고거래 환불을 받고 싶어요.",
        "status": "completed",
        "result": {"answer": "임시 답변"},
        "updated_at": "2026-09-09T00:00:00+00:00",
    }


def test_guest_history_is_ttl_bound_and_never_uses_a_database(monkeypatch) -> None:
    monkeypatch.setattr(guest_session_service, "get_settings", memory_settings)
    service = GuestSessionService()

    assert asyncio.run(service.save_analysis("guest-1", run("run-1"))) == 3600
    items, expires_in = asyncio.run(service.list_analyses("guest-1"))

    assert [item["run_id"] for item in items] == ["run-1"]
    assert 0 < expires_in <= 3600
    asyncio.run(service.clear("guest-1"))
    assert asyncio.run(service.list_analyses("guest-1"))[0] == []


def test_guest_history_replaces_a_retry_with_the_same_run_id(monkeypatch) -> None:
    monkeypatch.setattr(guest_session_service, "get_settings", memory_settings)
    service = GuestSessionService()

    asyncio.run(service.save_analysis("guest-1", run("run-1")))
    changed = run("run-1")
    changed["result"] = {"answer": "재시도 결과"}
    asyncio.run(service.save_analysis("guest-1", changed))

    items, _ = asyncio.run(service.list_analyses("guest-1"))
    assert len(items) == 1
    assert items[0]["result"]["answer"] == "재시도 결과"
