from datetime import datetime, timedelta
from uuid import uuid4


def sort_questions(questions: list[dict]) -> list[dict]:
    """답변 대기를 먼저, 각 상태 안에서는 최신 질문을 먼저 보여준다."""
    status_order = {"PENDING": 0, "ANSWERED": 1}
    return sorted(
        questions,
        key=lambda item: (
            status_order.get(item["status"], 2),
            -datetime.fromisoformat(item["created_at"]).timestamp(),
            item["id"],
        ),
    )


def paginate_questions(questions: list[dict], page: int, page_size: int = 10) -> dict:
    page_size = max(1, min(page_size, 50))
    total_items = len(questions)
    total_pages = max(1, (total_items + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))
    start = (page - 1) * page_size
    return {
        "items": questions[start : start + page_size],
        "page": page,
        "page_size": page_size,
        "total_items": total_items,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_previous": page > 1,
    }


def create_question(user: dict, category: str, title: str, content: str, is_public: bool) -> dict:
    now = datetime.now().replace(microsecond=0)
    return {
        "id": f"question-{uuid4()}",
        "owner_id": user["id"],
        "owner_role": user["role"],
        "display_name": user["display_name"],
        "category": category,
        "title": title.strip(),
        "content": content.strip(),
        "visibility": "PUBLIC" if is_public else "PRIVATE",
        "status": "PENDING",
        "answer": None,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "expires_at": (now + timedelta(days=7)).isoformat() if user["role"] == "GUEST" else None,
    }


def can_edit_question(question: dict, user: dict) -> bool:
    return question["owner_id"] == user["id"]


def filter_public_questions(questions: list[dict], category: str, status: str, query: str) -> list[dict]:
    normalized = query.strip().lower()
    results = []
    for item in questions:
        if item["visibility"] != "PUBLIC":
            continue
        if category != "all" and item["category"] != category:
            continue
        if status != "all" and item["status"] != status:
            continue
        if normalized and normalized not in f"{item['title']} {item['content']}".lower():
            continue
        results.append(item)
    return sort_questions(results)
