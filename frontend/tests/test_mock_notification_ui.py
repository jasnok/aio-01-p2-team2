from pathlib import Path

from streamlit.testing.v1 import AppTest

from frontend.services.mock_notification_service import unread_count


APP = Path(__file__).parents[1] / "app.py"


def test_analysis_creates_notification_and_read_delete_actions_work() -> None:
    app = AppTest.from_file(str(APP)).run(timeout=20)
    assert unread_count(app.session_state["notifications"]) == 1
    app.button(key="category-labor").click().run(timeout=20)
    app.text_area(key="question_message").set_value("퇴직했는데 퇴직금을 받지 못했습니다.")
    next(button for button in app.button if button.label == "✦ 사례 분석하기").click().run(timeout=20)

    notification = app.session_state["notifications"][-1]
    assert notification["type"] == "ANALYSIS_COMPLETED"
    assert unread_count(app.session_state["notifications"]) == 2

    app.button(key=f"notification-read-{notification['id']}").click().run(timeout=20)
    assert notification["is_read"] is True
    app.button(key=f"notification-delete-{notification['id']}").click().run(timeout=20)
    assert all(item["id"] != notification["id"] for item in app.session_state["notifications"])


def test_error_analysis_creates_error_notification() -> None:
    app = AppTest.from_file(str(APP)).run(timeout=20)
    app.button(key="category-housing").click().run(timeout=20)
    app.session_state["mock_scenario"] = "mcp_error"
    app.text_area(key="question_message").set_value("보증금 판례 검색 오류를 확인합니다.")
    next(button for button in app.button if button.label == "✦ 사례 분석하기").click().run(timeout=20)
    notification = app.session_state["notifications"][-1]
    assert notification["type"] == "ANALYSIS_FAILED"
    assert notification["severity"] == "error"


def test_notification_target_opens_related_question_screen() -> None:
    app = AppTest.from_file(str(APP)).run(timeout=20)
    app.button(key="category-housing").click().run(timeout=20)
    app.sidebar.button(key="nav-faq").click().run(timeout=20)
    app.text_input(key="new-question-title").set_value("알림 이동 질문")
    app.text_area(key="new-question-content").set_value("알림 관련 화면 이동을 확인하기 위한 질문입니다.")
    app.text_input(key="new-question-password").set_value("1234")
    app.text_input(key="new-question-password-confirm").set_value("1234")
    app.checkbox(key="new-question-privacy").check()
    next(button for button in app.button if button.label == "질문 등록").click().run(timeout=20)

    notification = app.session_state["notifications"][-1]
    assert notification["type"] == "QUESTION_CREATED"
    app.session_state["selected_feature"] = "analysis"
    app.button(key=f"notification-open-{notification['id']}").click().run(timeout=20)
    assert app.session_state["selected_feature"] == "faq"
    assert notification["is_read"] is True
