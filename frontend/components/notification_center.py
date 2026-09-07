from datetime import datetime

import streamlit as st

from frontend.services.mock_notification_service import (
    SEVERITY_ICONS,
    delete_notification,
    delete_read_notifications,
    mark_all_read,
    mark_read,
    sort_notifications,
)


def _format_time(value: str) -> str:
    return datetime.fromisoformat(value).strftime("%m-%d %H:%M")


def _mark_read(notification_id: str) -> None:
    mark_read(st.session_state.notifications, notification_id)


def _mark_all_read() -> None:
    mark_all_read(st.session_state.notifications)


def _delete(notification_id: str) -> None:
    st.session_state.notifications = delete_notification(st.session_state.notifications, notification_id)


def _delete_read() -> None:
    st.session_state.notifications = delete_read_notifications(st.session_state.notifications)


def _open_target(notification: dict) -> None:
    mark_read(st.session_state.notifications, notification["id"])
    target_type = notification.get("target_type")
    category = notification.get("category")
    if category:
        st.session_state.selected_category = category
        st.session_state.current_page = "workspace"
    if target_type == "analysis":
        st.session_state.selected_feature = "analysis"
    elif target_type == "question":
        st.session_state.selected_feature = "faq"
        st.session_state.question_page = 1
    elif target_type == "history":
        st.session_state.selected_feature = "history"


def render_notification_center() -> None:
    st.markdown("### 🔔 알림")
    st.caption("현재 브라우저 Session의 Mock 알림입니다. 실제 저장이나 외부 전송은 하지 않습니다.")
    notifications = sort_notifications(st.session_state.notifications)
    if not notifications:
        st.info("새로운 알림이 없습니다.")
        return

    action_columns = st.columns(2)
    action_columns[0].button("모두 읽음", key="notification-read-all", on_click=_mark_all_read, use_container_width=True)
    action_columns[1].button("읽은 알림 삭제", key="notification-delete-read", on_click=_delete_read, use_container_width=True)

    for notification in notifications:
        icon = SEVERITY_ICONS[notification["severity"]]
        unread_label = " · 새 알림" if not notification["is_read"] else ""
        with st.container(border=True):
            st.markdown(f"**{icon} {notification['title']}**")
            st.caption(f"{_format_time(notification['created_at'])}{unread_label}")
            st.write(notification["message"])
            columns = st.columns(3)
            if not notification["is_read"]:
                columns[0].button(
                    "읽음",
                    key=f"notification-read-{notification['id']}",
                    on_click=_mark_read,
                    args=(notification["id"],),
                    use_container_width=True,
                )
            if notification.get("target_type"):
                columns[1].button(
                    "관련 화면",
                    key=f"notification-open-{notification['id']}",
                    on_click=_open_target,
                    args=(notification,),
                    use_container_width=True,
                )
            columns[2].button(
                "삭제",
                key=f"notification-delete-{notification['id']}",
                on_click=_delete,
                args=(notification["id"],),
                use_container_width=True,
            )
