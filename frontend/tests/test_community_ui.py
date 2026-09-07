from pathlib import Path

from streamlit.testing.v1 import AppTest

from frontend.data.mock_community import ROLE_USERS


APP = Path(__file__).parents[1] / "app.py"


def _open_housing_workspace() -> AppTest:
    app = AppTest.from_file(str(APP)).run(timeout=20)
    app.button(key="category-housing").click().run(timeout=20)
    return app


def test_public_question_board_paginates_and_guest_can_delete_own_question() -> None:
    app = _open_housing_workspace()
    app.sidebar.button(key="nav-faq").click().run(timeout=20)

    assert app.session_state["question_page"] == 1
    assert app.button(key="question-next")
    first_page_titles = [item["title"] for item in app.session_state["public_questions"] if item["status"] == "PENDING"][:10]
    app.button(key="question-next").click().run(timeout=20)
    assert app.session_state["question_page"] == 2
    assert app.button(key="question-page-1")

    app.button(key="question-page-1").click().run(timeout=20)
    assert app.session_state["question_page"] == 1
    assert first_page_titles
    before = len(app.session_state["public_questions"])
    app.button(key="delete-question-1002").click().run(timeout=20)
    assert len(app.session_state["public_questions"]) == before - 1


def test_guest_can_create_and_edit_own_pending_question() -> None:
    app = _open_housing_workspace()
    app.sidebar.button(key="nav-faq").click().run(timeout=20)
    before = len(app.session_state["public_questions"])
    app.text_input(key="new-question-title").set_value("보증금 질문")
    app.text_area(key="new-question-content").set_value("보증금 반환을 위해 어떤 자료가 필요한지 궁금합니다.")
    app.checkbox(key="new-question-privacy").check()
    next(button for button in app.button if button.label == "질문 등록").click().run(timeout=20)

    assert len(app.session_state["public_questions"]) == before + 1
    created = app.session_state["public_questions"][-1]
    app.button(key=f"edit-{created['id']}").click().run(timeout=20)
    next(item for item in app.text_input if item.label == "제목 수정").set_value("수정된 보증금 질문")
    next(button for button in app.button if button.label == "수정 저장").click().run(timeout=20)
    assert app.session_state["public_questions"][-1]["title"] == "수정된 보증금 질문"


def test_admin_role_exposes_admin_faq_screen() -> None:
    app = _open_housing_workspace()
    app.session_state["mock_role"] = "ADMIN"
    app.session_state["current_user"] = ROLE_USERS["ADMIN"].copy()
    app.run(timeout=20)

    assert app.sidebar.button(key="nav-admin-faq")
    app.sidebar.button(key="nav-admin-faq").click().run(timeout=20)
    assert not app.exception
    assert any("관리자 FAQ 관리" in item.value for item in app.markdown)


def test_unified_history_contains_analysis_and_own_questions() -> None:
    app = _open_housing_workspace()
    app.text_area[0].set_value("계약이 끝났는데 집주인이 보증금을 돌려주지 않습니다.")
    next(button for button in app.button if button.label == "✦ 사례 분석하기").click().run(timeout=20)
    app.sidebar.button(key="nav-history").click().run(timeout=20)

    assert not app.exception
    assert app.session_state["session_history"]
    assert any("통합 질의 이력" in item.value for item in app.markdown)
