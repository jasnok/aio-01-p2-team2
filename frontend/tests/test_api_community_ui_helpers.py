from frontend.components.api_community_faq import _sort_question_items


def test_questions_are_pending_first_and_newest_within_status() -> None:
    items = [
        {"id": "answered-new", "status": "ANSWERED", "created_at": "2026-09-07T12:00:00"},
        {"id": "pending-old", "status": "PENDING", "created_at": "2026-09-06T12:00:00"},
        {"id": "pending-new", "status": "PENDING", "created_at": "2026-09-07T13:00:00"},
        {"id": "answered-old", "status": "ANSWERED", "created_at": "2026-09-05T12:00:00"},
    ]

    assert [item["id"] for item in _sort_question_items(items)] == [
        "pending-new",
        "pending-old",
        "answered-new",
        "answered-old",
    ]
