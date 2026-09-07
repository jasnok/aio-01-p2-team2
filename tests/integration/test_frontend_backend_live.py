import os
from uuid import uuid4

import httpx
import pytest
from streamlit.testing.v1 import AppTest
from frontend.clients import backend_client


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_FRONTEND_BACKEND", "false").lower() != "true",
    reason="실제 Frontend-Backend 통합 검사는 명시적으로 실행합니다.",
)

BACKEND_URL = os.getenv("BACKEND_API_URL", "http://192.100.200.195:8000").rstrip("/")
REQUIRED_PATHS = {
    "/health",
    "/api/legal/questions",
    "/api/legal/laws",
    "/api/legal/cases",
    "/api/legal/terms",
    "/api/catalog/{category}",
}


def test_backend_health_and_required_contract() -> None:
    health = httpx.get(f"{BACKEND_URL}/health", timeout=5)
    health.raise_for_status()
    assert health.json()["status"] == "ok"

    openapi = httpx.get(f"{BACKEND_URL}/openapi.json", timeout=5)
    openapi.raise_for_status()
    assert REQUIRED_PATHS <= set(openapi.json()["paths"])


def test_api_mode_full_legal_ui_flow(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRONTEND_DATA_MODE", "api")
    monkeypatch.setenv("BACKEND_API_URL", BACKEND_URL)
    app = AppTest.from_file("frontend/app.py").run(timeout=20)
    assert not app.exception

    app.button(key="category-housing").click().run(timeout=20)
    app.text_area(key="question_message").set_value("계약이 끝났는데 보증금을 돌려받지 못했습니다.")
    next(button for button in app.button if button.label == "✦ 사례 분석하기").click().run(timeout=30)
    assert not app.exception
    assert app.session_state["last_result"]["status"] == "completed"
    assert app.session_state["last_result"]["request_id"]

    app.sidebar.button(key="nav-laws").click().run(timeout=20)
    app.text_input(key="law_query").set_value("보증금")
    next(button for button in app.button if button.label == "검색하기").click().run(timeout=20)
    assert not app.exception
    assert app.session_state["law_results"] is not None

    app.sidebar.button(key="nav-cases").click().run(timeout=20)
    app.text_input(key="case_query").set_value("보증금 반환")
    next(button for button in app.button if button.label == "검색하기").click().run(timeout=20)
    assert not app.exception
    assert app.session_state["case_results"] is not None

    app.sidebar.button(key="nav-terms").click().run(timeout=20)
    assert not app.exception
    assert any("내용증명" in item.value for item in app.markdown)

    app.sidebar.button(key="nav-faq").click().run(timeout=20)
    assert not app.exception
    assert any("자주 하는 질문" in item.value for item in app.markdown)

    app.sidebar.button(key="nav-history").click().run(timeout=20)
    assert not app.exception
    assert any("통합 질의 이력" in item.value for item in app.markdown)


def test_auth_and_guest_community_crud() -> None:
    login = backend_client.login("user@lawpath.demo", "Demo1234!")
    token = login["session_token"]
    assert backend_client.get_current_user(token, "unused")["authenticated"] is True
    backend_client.logout(token)

    guest_id = f"guest-live-{uuid4()}"
    question = None
    comment = None
    try:
        assert backend_client.get_current_user(None, guest_id)["authenticated"] is False
        assert "items" in backend_client.list_faqs("housing")
        question = backend_client.create_question_api(
            None,
            guest_id,
            {
                "category": "housing",
                "title": "Frontend 통합 자동 확인",
                "content": "Frontend와 Backend 게시판 연동을 확인하는 테스트 내용입니다.",
                "post_password": "2468",
                "visibility": "PUBLIC",
                "privacy_confirmed": True,
            },
        )
        comment = backend_client.create_comment_api(None, guest_id, question["id"], "댓글 연동 자동 확인입니다.", "1357")
        assert backend_client.get_question(None, guest_id, question["id"])["is_owner"] is True
        assert backend_client.list_comments(None, guest_id, question["id"])["items"]
        assert backend_client.list_history(None, guest_id, page=1, page_size=10, type="all")["items"]
        notifications = backend_client.list_notifications(None, guest_id)["items"]
        assert notifications
        backend_client.mark_notification_read(None, guest_id, notifications[0]["id"])
    finally:
        if question and comment:
            backend_client.delete_comment_api(None, guest_id, question["id"], comment["id"], "1357")
        if question:
            backend_client.delete_question_api(None, guest_id, question["id"], "2468")
        for item in backend_client.list_notifications(None, guest_id).get("items", []):
            backend_client.delete_notification_api(None, guest_id, item["id"])
        for item in backend_client.list_history(None, guest_id, page=1, page_size=50, type="all").get("items", []):
            backend_client.delete_history(None, guest_id, item["id"])


def test_admin_faq_crud() -> None:
    login = backend_client.login("admin@lawpath.demo", "Admin1234!")
    token = login["session_token"]
    faq = None
    try:
        faq = backend_client.create_admin_faq(
            token,
            {"category": "housing", "question": "Frontend 관리자 FAQ 자동 확인", "answer": "연동 확인 후 삭제되는 항목입니다.", "is_active": False, "is_pinned": False, "display_order": 999},
        )
        assert any(item["id"] == faq["id"] for item in backend_client.list_admin_faqs(token)["items"])
        updated = backend_client.update_admin_faq(token, faq["id"], {**faq, "answer": "수정 확인 후 삭제됩니다."})
        assert updated["answer"] == "수정 확인 후 삭제됩니다."
    finally:
        if faq:
            backend_client.delete_admin_faq(token, faq["id"])
        backend_client.logout(token)
