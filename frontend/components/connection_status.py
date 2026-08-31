from datetime import datetime

import streamlit as st

from frontend.clients.backend_client import BackendClientError, get_backend_health
from frontend.core.config import get_frontend_settings


def render_connection_status() -> None:
    settings = get_frontend_settings()
    st.subheader("서버 연결")
    st.code(settings.normalized_backend_url, language=None)

    if st.button("연결 상태 확인", use_container_width=True):
        try:
            health = get_backend_health()
            dependencies = health.get("dependencies", {})
            st.success("Backend 연결됨")
            st.write(f"MCP: `{dependencies.get('mcp', 'unknown')}`")
            st.write(f"Database: `{dependencies.get('database', 'unknown')}`")
            st.write(f"Redis: `{dependencies.get('redis', 'unknown')}`")
            st.caption(f"확인 시각: {datetime.now().strftime('%H:%M:%S')}")
        except BackendClientError as error:
            st.error(error.user_message)

