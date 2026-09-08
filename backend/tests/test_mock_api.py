from fastapi.testclient import TestClient
import asyncio

from backend.app.main import app
from backend.app.schemas.legal import LegalQuestionResponse
from backend.app.services import agent_run_service
from backend.app.services.mock_store import now, store


client = TestClient(app)


def login(email: str, password: str) -> dict:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['session_token']}"}


def question_body(**overrides) -> dict:
    return {
        "category": "housing",
        "title": "보증금 반환을 확인하고 싶습니다",
        "content": "계약이 종료되었는데 보증금 반환에 필요한 자료가 궁금합니다.",
        "post_password": "1234",
        "privacy_confirmed": True,
        **overrides,
    }


def test_demo_auth_and_admin_faq_authorization() -> None:
    user_headers = login("user@lawpath.demo", "Demo1234!")
    assert client.get("/api/auth/me", headers=user_headers).json()["user"]["role"] == "USER"
    assert client.get("/api/admin/faqs", headers=user_headers).status_code == 403
    admin_headers = login("admin@lawpath.demo", "Admin1234!")
    assert client.get("/api/admin/faqs", headers=admin_headers).status_code == 200


def test_private_question_is_hidden_from_other_guest_and_public_question_is_open() -> None:
    owner = {"X-Guest-Id": "guest-owner"}
    created = client.post("/api/questions", headers=owner, json=question_body())
    assert created.status_code == 201
    question_id = created.json()["id"]
    denied = client.get(f"/api/questions/{question_id}", headers={"X-Guest-Id": "guest-other"})
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "FORBIDDEN"
    public = client.post("/api/questions", headers=owner, json=question_body(visibility="PUBLIC", title="공개 보증금 질문"))
    assert client.get(f"/api/questions/{public.json()['id']}", headers={"X-Guest-Id": "guest-other"}).status_code == 200


def test_comments_notifications_and_owner_rules() -> None:
    headers = {"X-Guest-Id": "guest-comment-owner"}
    question = client.post("/api/questions", headers=headers, json=question_body(visibility="PUBLIC", title="댓글 테스트 질문")).json()
    other = {"X-Guest-Id": "guest-comment-other"}
    comment = client.post(f"/api/questions/{question['id']}/comments", headers=other, json={"content": "도움이 되는 댓글", "comment_password": "5678"})
    assert comment.status_code == 201
    assert client.patch(f"/api/questions/{question['id']}/comments/{comment.json()['id']}", headers=headers, json={"content": "다른 사람이 수정", "comment_password": "5678"}).status_code == 403
    notifications = client.get("/api/notifications", headers=headers).json()["items"]
    assert any(item["type"] == "COMMENT_CREATED" for item in notifications)


def test_legal_idempotency_returns_first_result(monkeypatch) -> None:
    payload = {"session_id": "guest-idempotent", "category": "labor", "question": "퇴직금을 받지 못했습니다."}
    headers = {"Idempotency-Key": "same-request-key", "X-Guest-Id": "guest-idempotent"}
    first = client.post("/api/legal/questions", headers=headers, json=payload)
    second = client.post("/api/legal/questions", headers=headers, json=payload)
    assert first.status_code == second.status_code == 200
    assert first.json()["request_id"] == second.json()["request_id"]


def test_validation_envelope_has_request_id() -> None:
    response = client.post("/api/questions", json={})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "VALIDATION_ERROR"
    assert response.json()["detail"]["request_id"].startswith("req-")


def test_admin_can_delete_any_question_only_with_audit_reason() -> None:
    owner = {"X-Guest-Id": "guest-delete-owner"}
    question = client.post("/api/questions", headers=owner, json=question_body()).json()
    admin = login("admin@lawpath.demo", "Admin1234!")
    missing_reason = client.request("DELETE", f"/api/questions/{question['id']}", headers=admin, json={})
    assert missing_reason.status_code == 422
    deleted = client.request("DELETE", f"/api/questions/{question['id']}", headers=admin, json={"reason": "신고된 게시글 운영 조치"})
    assert deleted.status_code == 204
    audit = store.audit_logs[-1]
    assert audit["actor_id"] == "admin-demo"
    assert audit["target_id"] == question["id"]
    assert audit["reason"] == "신고된 게시글 운영 조치"


def test_notification_read_items_and_agent_run_sse_contract(monkeypatch) -> None:
    async def fake_answer(request, event_callback=None):
        return LegalQuestionResponse(
            request_id="req-agent-run", agent_id=request.category,
            termination_reason="model_finished", question_summary="테스트 요약",
            answer="테스트 답변", is_mock=False,
        )

    monkeypatch.setattr(agent_run_service, "answer_question_from_mcp", fake_answer)
    # TestClient의 요청 루프와 별개로 작업 본문을 명시 실행해 저장 순서를 검사한다.
    monkeypatch.setattr("backend.app.routers.mock_api.start_run", lambda _run_id: None)
    guest = {"X-Guest-Id": "guest-run"}
    client.post("/api/questions", headers=guest, json=question_body())
    assert client.delete("/api/notifications/read-items", headers=guest).status_code == 204
    created = client.post("/api/agent-runs", headers=guest | {"Idempotency-Key": "run-key-001"}, json={"category": "labor", "question": "퇴직금을 받지 못했습니다."})
    assert created.status_code == 202
    run_id = created.json()["run_id"]
    assert created.json()["status"] == "queued"
    repeated = client.post("/api/agent-runs", headers=guest | {"Idempotency-Key": "run-key-001"}, json={"category": "labor", "question": "퇴직금을 받지 못했습니다."})
    assert repeated.json()["run_id"] == run_id
    conflict = client.post("/api/agent-runs", headers=guest | {"Idempotency-Key": "run-key-001"}, json={"category": "labor", "question": "다른 질문입니다."})
    assert conflict.status_code == 409

    asyncio.run(agent_run_service.execute_run(run_id))
    status = client.get(f"/api/agent-runs/{run_id}", headers=guest).json()
    assert status["status"] == "completed"
    assert status["result"]["is_mock"] is False
    assert store.agent_runs[run_id]["events"][-1]["event"] == "run.completed"
    assert "data:" in __import__("backend.app.routers.mock_api", fromlist=["sse_event"]).sse_event(store.agent_runs[run_id]["events"][-1])
    replay = client.get(f"/api/agent-runs/{run_id}/events", headers=guest | {"Last-Event-ID": "1"})
    assert replay.headers["content-type"].startswith("text/event-stream")
    assert "id: 2" in replay.text and "run.completed" in replay.text
    assert client.get(f"/api/agent-runs/{run_id}", headers={"X-Guest-Id": "someone-else"}).status_code == 404


def test_agent_run_stops_for_clarification_and_hides_internal_failure(monkeypatch) -> None:
    async def clarification(request, event_callback=None):
        return LegalQuestionResponse(
            request_id="req-clarify", agent_id=request.category, status="stopped",
            termination_reason="needs_clarification", question_summary="추가 정보 필요",
            answer="추가 정보를 알려주세요.", follow_up_questions=["계약 종료일을 알려주세요."],
            is_mock=False,
        )

    monkeypatch.setattr(agent_run_service, "answer_question_from_mcp", clarification)
    monkeypatch.setattr("backend.app.routers.mock_api.start_run", lambda _run_id: None)
    headers = {"X-Guest-Id": "guest-clarification", "Idempotency-Key": "clarification-key"}
    run_id = client.post("/api/agent-runs", headers=headers, json={"category": "housing", "question": "보증금이 걱정됩니다."}).json()["run_id"]
    asyncio.run(agent_run_service.execute_run(run_id))
    run = client.get(f"/api/agent-runs/{run_id}", headers=headers).json()
    assert run["status"] == "stopped"
    assert run["result"]["follow_up_questions"] == ["계약 종료일을 알려주세요."]

    async def broken(request, event_callback=None):
        raise RuntimeError("postgres password=secret must not escape")

    monkeypatch.setattr(agent_run_service, "answer_question_from_mcp", broken)
    headers["Idempotency-Key"] = "failure-key"
    failed_id = client.post("/api/agent-runs", headers=headers, json={"category": "housing", "question": "보증금이 걱정됩니다."}).json()["run_id"]
    asyncio.run(agent_run_service.execute_run(failed_id))
    failed = client.get(f"/api/agent-runs/{failed_id}", headers=headers).json()
    assert failed["status"] == "failed"
    assert failed["error"]["code"] == "ANALYSIS_FAILED"
    assert "secret" not in failed["error"]["message"]


def test_expired_session_uses_common_error_code() -> None:
    headers = login("user@lawpath.demo", "Demo1234!")
    token = headers["Authorization"].removeprefix("Bearer ")
    store.sessions[token]["expires_at"] = now().replace(year=2000)
    response = client.get("/api/auth/me", headers=headers)
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "AUTH_SESSION_EXPIRED"
