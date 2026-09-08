from pathlib import Path

from streamlit.testing.v1 import AppTest

from frontend.data.mock_community import ROLE_USERS


APP = Path(__file__).parents[1] / "app.py"


def _open_housing_workspace() -> AppTest:
    app = AppTest.from_file(str(APP)).run(timeout=20)
    app.button(key="category-housing").click().run(timeout=20)
    return app


def test_public_question_board_paginates() -> None:
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


def test_guest_can_create_and_edit_own_pending_question() -> None:
    app = _open_housing_workspace()
    app.sidebar.button(key="nav-faq").click().run(timeout=20)
    before = len(app.session_state["public_questions"])
    app.text_input(key="new-question-title").set_value("보증금 질문")
    app.text_area(key="new-question-content").set_value("보증금 반환을 위해 어떤 자료가 필요한지 궁금합니다.")
    app.text_input(key="new-question-password").set_value("1234")
    app.text_input(key="new-question-password-confirm").set_value("1234")
    app.checkbox(key="new-question-privacy").check()
    next(button for button in app.button if button.label == "질문 등록").click().run(timeout=20)

    assert len(app.session_state["public_questions"]) == before + 1
    created = app.session_state["public_questions"][-1]
    assert created["content_visibility"] == "OWNER_ONLY"
    assert created["password_hash"] != "1234"

    app.text_input(key=f"unlock-password-{created['id']}").set_value("1234")
    next(button for button in app.button if button.label == "내 글 확인").click().run(timeout=20)
    assert created["id"] in app.session_state["unlocked_question_ids"]

    app.button(key=f"edit-{created['id']}").click().run(timeout=20)
    next(item for item in app.text_input if item.label == "제목 수정").set_value("수정된 보증금 질문")
    next(button for button in app.button if button.label == "수정 저장").click().run(timeout=20)
    assert app.session_state["public_questions"][-1]["title"] == "수정된 보증금 질문"


def test_guest_can_unlock_and_delete_own_question() -> None:
    app = _open_housing_workspace()
    app.sidebar.button(key="nav-faq").click().run(timeout=20)
    app.text_input(key="new-question-title").set_value("삭제할 질문")
    app.text_area(key="new-question-content").set_value("본인 질문 삭제 동작을 확인하기 위한 내용입니다.")
    app.text_input(key="new-question-password").set_value("1234")
    app.text_input(key="new-question-password-confirm").set_value("1234")
    app.checkbox(key="new-question-privacy").check()
    next(button for button in app.button if button.label == "질문 등록").click().run(timeout=20)
    created = app.session_state["public_questions"][-1]

    app.text_input(key=f"unlock-password-{created['id']}").set_value("1234")
    next(button for button in app.button if button.label == "내 글 확인").click().run(timeout=20)
    app.button(key=f"delete-{created['id']}").click().run(timeout=20)
    assert all(item["id"] != created["id"] for item in app.session_state["public_questions"])


def test_question_title_is_public_but_content_requires_owner_password() -> None:
    app = _open_housing_workspace()
    app.sidebar.button(key="nav-faq").click().run(timeout=20)
    secret_content = "작성자만 확인해야 하는 비공개 질문 내용입니다."
    app.text_input(key="new-question-title").set_value("공개되는 글 제목")
    app.text_area(key="new-question-content").set_value(secret_content)
    app.text_input(key="new-question-password").set_value("2468")
    app.text_input(key="new-question-password-confirm").set_value("2468")
    app.checkbox(key="new-question-privacy").check()
    next(button for button in app.button if button.label == "질문 등록").click().run(timeout=20)
    created = app.session_state["public_questions"][-1]

    visible_before = "\n".join(item.value for item in app.markdown)
    assert "공개되는 글 제목" in visible_before
    assert secret_content not in visible_before

    app.text_input(key=f"unlock-password-{created['id']}").set_value("wrong")
    next(button for button in app.button if button.label == "내 글 확인").click().run(timeout=20)
    assert created["id"] not in app.session_state["unlocked_question_ids"]
    assert any("올바르지 않습니다" in item.value for item in app.error)

    app.text_input(key=f"unlock-password-{created['id']}").set_value("2468")
    next(button for button in app.button if button.label == "내 글 확인").click().run(timeout=20)
    assert created["id"] in app.session_state["unlocked_question_ids"]
    assert any(secret_content in item.value for item in app.markdown)


def test_guest_can_create_public_question_and_comment_with_password() -> None:
    app = _open_housing_workspace()
    app.sidebar.button(key="nav-faq").click().run(timeout=20)
    app.text_input(key="new-question-title").set_value("댓글 테스트 공개 질문")
    app.text_area(key="new-question-content").set_value("누구나 내용을 보고 댓글을 작성할 수 있는 공개 질문입니다.")
    app.text_input(key="new-question-password").set_value("1234")
    app.text_input(key="new-question-password-confirm").set_value("1234")
    app.checkbox(key="new-question-private").uncheck()
    app.checkbox(key="new-question-privacy").check()
    next(button for button in app.button if button.label == "질문 등록").click().run(timeout=20)
    created = app.session_state["public_questions"][-1]

    assert created["visibility"] == "PUBLIC"
    assert created["content_visibility"] == "PUBLIC"
    app.text_area(key=f"comment-content-{created['id']}").set_value("비회원이 작성한 공개 댓글입니다.")
    app.text_input(key=f"comment-password-{created['id']}").set_value("5678")
    app.button(key=f"FormSubmitter:comment-create-{created['id']}-댓글 등록").click().run(timeout=20)

    assert len(created["comments"]) == 1
    assert created["comments"][0]["content"] == "비회원이 작성한 공개 댓글입니다."
    assert created["comments"][0]["password_hash"] != "5678"
    assert any(item["type"] == "COMMENT_CREATED" for item in app.session_state["notifications"])


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
    app.text_area(key="question_message").set_value("계약이 끝났는데 집주인이 보증금을 돌려주지 않습니다.")
    next(button for button in app.button if button.label == "✦ 사례 분석하기").click().run(timeout=20)
    app.sidebar.button(key="nav-history").click().run(timeout=20)

    assert not app.exception
    assert app.session_state["session_history"]
    assert any("통합 질의 이력" in item.value for item in app.markdown)
