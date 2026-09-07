from frontend.data.mock_community import ROLE_USERS, build_mock_questions
from frontend.services.mock_community_service import can_edit_question, create_question, filter_public_questions, paginate_questions, sort_questions


def test_questions_are_sorted_pending_first_then_latest_and_paginated() -> None:
    questions = sort_questions(build_mock_questions())
    first = paginate_questions(questions, page=1, page_size=10)
    last = paginate_questions(questions, page=3, page_size=10)

    assert first["total_items"] == 23
    assert first["total_pages"] == 3
    assert len(first["items"]) == 10
    assert len(last["items"]) == 3
    statuses = [item["status"] for item in questions]
    assert statuses == sorted(statuses, key={"PENDING": 0, "ANSWERED": 1}.get)
    pending = [item for item in questions if item["status"] == "PENDING"]
    answered = [item for item in questions if item["status"] == "ANSWERED"]
    assert pending == sorted(pending, key=lambda item: item["created_at"], reverse=True)
    assert answered == sorted(answered, key=lambda item: item["created_at"], reverse=True)


def test_page_is_corrected_when_requested_page_is_out_of_range() -> None:
    result = paginate_questions(build_mock_questions()[:3], page=99, page_size=10)
    assert result["page"] == 1
    assert not result["has_next"]


def test_public_filters_and_owner_permission() -> None:
    questions = build_mock_questions()
    questions[0]["visibility"] = "PRIVATE"
    filtered = filter_public_questions(questions, "housing", "all", "보증금")

    assert filtered
    assert all(item["category"] == "housing" and item["visibility"] == "PUBLIC" for item in filtered)
    assert can_edit_question(questions[2], ROLE_USERS["GUEST"])
    assert not can_edit_question(questions[2], ROLE_USERS["USER"])


def test_guest_question_has_expiry_and_member_question_does_not() -> None:
    guest = create_question(ROLE_USERS["GUEST"], "housing", "보증금 질문", "보증금 반환에 필요한 자료가 궁금합니다.", True)
    member = create_question(ROLE_USERS["USER"], "housing", "보증금 질문", "보증금 반환에 필요한 자료가 궁금합니다.", True)

    assert guest["expires_at"] is not None
    assert member["expires_at"] is None
    assert guest["visibility"] == "PUBLIC"
