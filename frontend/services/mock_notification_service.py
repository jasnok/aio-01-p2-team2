from datetime import datetime
from uuid import uuid4


SEVERITY_ICONS = {"info": "🔵", "success": "✅", "warning": "⚠️", "error": "🔴"}


def create_notification(
    notification_type: str,
    title: str,
    message: str,
    *,
    severity: str = "info",
    target_type: str | None = None,
    target_id: str | None = None,
    category: str | None = None,
) -> dict:
    if severity not in SEVERITY_ICONS:
        raise ValueError("지원하지 않는 알림 중요도입니다.")
    return {
        "id": f"notification-{uuid4()}",
        "type": notification_type,
        "title": title,
        "message": message,
        "severity": severity,
        "target_type": target_type,
        "target_id": target_id,
        "category": category,
        "created_at": datetime.now().isoformat(),
        "is_read": False,
    }


def add_notification(notifications: list[dict], *args, **kwargs) -> dict:
    notification = create_notification(*args, **kwargs)
    notifications.append(notification)
    return notification


def sort_notifications(notifications: list[dict]) -> list[dict]:
    # Windows에서 연속 생성 시 created_at이 같을 수 있어 삽입 역순을 최신순 보조 기준으로 사용한다.
    latest_first = sorted(reversed(notifications), key=lambda item: item["created_at"], reverse=True)
    return sorted(latest_first, key=lambda item: item["is_read"])


def unread_count(notifications: list[dict]) -> int:
    return sum(not item["is_read"] for item in notifications)


def mark_read(notifications: list[dict], notification_id: str) -> None:
    for notification in notifications:
        if notification["id"] == notification_id:
            notification["is_read"] = True
            return


def mark_all_read(notifications: list[dict]) -> None:
    for notification in notifications:
        notification["is_read"] = True


def delete_notification(notifications: list[dict], notification_id: str) -> list[dict]:
    return [item for item in notifications if item["id"] != notification_id]


def delete_read_notifications(notifications: list[dict]) -> list[dict]:
    return [item for item in notifications if not item["is_read"]]
