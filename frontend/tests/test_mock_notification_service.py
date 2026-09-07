from frontend.services.mock_notification_service import (
    add_notification,
    delete_notification,
    delete_read_notifications,
    mark_all_read,
    mark_read,
    sort_notifications,
    unread_count,
)


def test_notification_lifecycle() -> None:
    notifications = []
    first = add_notification(notifications, "FIRST", "첫 알림", "첫 내용")
    second = add_notification(notifications, "SECOND", "두 번째 알림", "두 번째 내용", severity="warning")

    assert unread_count(notifications) == 2
    assert sort_notifications(notifications)[0]["id"] == second["id"]
    mark_read(notifications, first["id"])
    assert unread_count(notifications) == 1
    assert sort_notifications(notifications)[0]["id"] == second["id"]

    mark_all_read(notifications)
    assert unread_count(notifications) == 0
    assert delete_read_notifications(notifications) == []


def test_delete_only_selected_notification() -> None:
    notifications = []
    first = add_notification(notifications, "FIRST", "첫 알림", "첫 내용")
    second = add_notification(notifications, "SECOND", "두 번째 알림", "두 번째 내용")
    remaining = delete_notification(notifications, first["id"])
    assert [item["id"] for item in remaining] == [second["id"]]


def test_notification_rejects_unknown_severity() -> None:
    notifications = []
    try:
        add_notification(notifications, "BAD", "잘못된 알림", "내용", severity="unknown")
    except ValueError as error:
        assert "중요도" in str(error)
    else:
        raise AssertionError("지원하지 않는 중요도를 허용했습니다.")
