from datetime import datetime

import streamlit as st

from frontend.clients import backend_client
from frontend.core.config import get_frontend_settings
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
    if get_frontend_settings().frontend_data_mode.lower() == "api":
        _render_api_notification_center()
        return
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


def _render_api_notification_center() -> None:
    token = st.session_state.auth_token
    guest_id = f"guest-{st.session_state.session_id}"
    st.markdown("### 🔔 알림")
    st.caption("Backend API에 저장된 현재 사용자 알림입니다.")
    try:
        payload = backend_client.list_notifications(token, guest_id)
    except backend_client.BackendClientError as error:
        st.error(error.user_message)
        return
    notifications = payload.get("items", [])
    if not notifications:
        st.info("새로운 알림이 없습니다.")
        return
    columns = st.columns(2)
    if columns[0].button("모두 읽음", key="api-notification-read-all", use_container_width=True):
        try:
            backend_client.mark_notifications_read(token, guest_id)
            st.rerun()
        except backend_client.BackendClientError as error:
            st.error(error.user_message)
    if columns[1].button("읽은 알림 삭제", key="api-notification-delete-read", use_container_width=True):
        try:
            backend_client.delete_read_notifications_api(token, guest_id)
            st.toast("읽은 알림을 삭제했습니다.", icon="🗑️")
            st.rerun()
        except backend_client.BackendClientError as error:
            # 신규 일괄 삭제 API가 아직 배포되지 않았거나 경로가 충돌하는
            # Backend와도 동작하도록 개별 삭제로 한 번 더 시도한다.
            read_items = [item for item in notifications if item.get("is_read")]
            failures = 0
            for item in read_items:
                try:
                    backend_client.delete_notification_api(token, guest_id, item["id"])
                except backend_client.BackendClientError:
                    failures += 1
            if read_items and failures == 0:
                st.toast("읽은 알림을 개별 삭제했습니다.", icon="🗑️")
                st.rerun()
            elif not read_items:
                st.info("삭제할 읽은 알림이 없습니다.")
            else:
                st.error(f"{error.user_message} 개별 삭제도 {failures}건 실패했습니다.")
    for notification in notifications:
        icon = SEVERITY_ICONS.get(notification.get("severity", "info"), "🔵")
        with st.container(border=True):
            st.markdown(f"**{icon} {notification['title']}**")
            st.caption(f"{_format_time(notification['created_at'])}{' · 새 알림' if not notification.get('is_read') else ''}")
            st.write(notification.get("message", ""))
            actions = st.columns(2)
            if not notification.get("is_read") and actions[0].button("읽음", key=f"api-notification-read-{notification['id']}"):
                try:
                    backend_client.mark_notification_read(token, guest_id, notification["id"])
                    st.rerun()
                except backend_client.BackendClientError as error:
                    st.error(error.user_message)
            if actions[1].button("삭제", key=f"api-notification-delete-{notification['id']}"):
                try:
                    backend_client.delete_notification_api(token, guest_id, notification["id"])
                    st.rerun()
                except backend_client.BackendClientError as error:
                    st.error(error.user_message)
