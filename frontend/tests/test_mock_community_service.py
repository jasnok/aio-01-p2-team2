from frontend.data.mock_community import ROLE_USERS, build_mock_questions
from frontend.services.mock_community_service import (
    can_comment_question,
    can_edit_question,
    can_manage_comment,
    can_view_question,
    create_comment,
    create_question,
    delete_comment,
    filter_public_questions,
    paginate_questions,
    sort_questions,
    update_comment,
    verify_comment_password,
    verify_question_password,
)
import pytest


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


def test_board_filters_titles_of_public_and_private_questions() -> None:
    questions = build_mock_questions()
    questions[0]["visibility"] = "PRIVATE"
    filtered = filter_public_questions(questions, "housing", "all", "보증금")

    assert filtered
    assert all(item["category"] == "housing" for item in filtered)
    assert any(item["visibility"] == "PRIVATE" for item in filtered)
    assert can_edit_question(questions[2], ROLE_USERS["GUEST"])
    assert not can_edit_question(questions[2], ROLE_USERS["USER"])


def test_guest_question_has_expiry_and_member_question_does_not() -> None:
    guest = create_question(ROLE_USERS["GUEST"], "housing", "보증금 질문", "보증금 반환에 필요한 자료가 궁금합니다.", True)
    member = create_question(ROLE_USERS["USER"], "housing", "보증금 질문", "보증금 반환에 필요한 자료가 궁금합니다.", True)

    assert guest["expires_at"] is not None
    assert member["expires_at"] is None
    assert guest["visibility"] == "PUBLIC"
    assert guest["content_visibility"] == "PUBLIC"
    assert guest["password_hash"] != "1234"
    assert verify_question_password(guest, "1234")
    assert not verify_question_password(guest, "wrong")


def test_search_reads_public_content_but_not_private_content() -> None:
    public_question = create_question(
        ROLE_USERS["USER"],
        "housing",
        "공개 제목",
        "내용에만있는공개검색어",
        True,
        "1234",
    )
    private_question = create_question(
        ROLE_USERS["USER"],
        "housing",
        "비밀 제목 검색어",
        "내용에만있는비밀검색어",
        False,
        "1234",
    )
    questions = [public_question, private_question]

    assert filter_public_questions(questions, "all", "all", "공개검색어")
    assert filter_public_questions(questions, "all", "all", "비밀 제목")
    assert filter_public_questions(questions, "all", "all", "비밀검색어") == []


def test_public_and_private_question_access_rules() -> None:
    author = ROLE_USERS["USER"]
    other = {**ROLE_USERS["USER"], "id": "member-other"}
    public_question = create_question(author, "housing", "공개 질문", "공개 질문 내용입니다.", True)
    private_question = create_question(author, "housing", "비밀 질문", "비밀 질문 내용입니다.", False)

    assert can_view_question(public_question, other)
    assert can_comment_question(public_question, ROLE_USERS["GUEST"])
    assert not can_view_question(private_question, other)
    assert not can_comment_question(private_question, other)
    assert not can_view_question(private_question, author)
    assert can_view_question(private_question, author, is_unlocked=True)
    assert can_comment_question(private_question, ROLE_USERS["ADMIN"])


def test_guest_comment_password_and_comment_crud_permissions() -> None:
    question = create_question(ROLE_USERS["USER"], "housing", "공개 질문", "공개 질문 내용입니다.", True)
    guest = ROLE_USERS["GUEST"]
    other_guest = {**guest, "id": "guest-other"}
    comment = create_comment(question, guest, "도움이 되는 공개 댓글입니다.", "5678")
    question["comments"].append(comment)

    assert comment["password_hash"] != "5678"
    assert verify_comment_password(comment, "5678")
    assert not can_manage_comment(comment, guest, "wrong")
    assert not can_manage_comment(comment, other_guest, "5678")
    assert not can_manage_comment(comment, ROLE_USERS["ADMIN"])
    with pytest.raises(PermissionError):
        update_comment(comment, guest, "수정을 시도합니다.", "wrong")

    update_comment(comment, guest, "수정된 공개 댓글입니다.", "5678")
    assert comment["content"] == "수정된 공개 댓글입니다."
    delete_comment(question, comment, ROLE_USERS["ADMIN"])
    assert question["comments"] == []
