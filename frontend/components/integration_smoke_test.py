from __future__ import annotations

import socket
from time import perf_counter
from urllib.parse import urlparse

import httpx
import streamlit as st

from frontend.core.config import get_frontend_settings


def _check_http(name: str, url: str, timeout: float = 3.0) -> dict:
    started = perf_counter()
    try:
        response = httpx.get(url, timeout=timeout)
        elapsed_ms = round((perf_counter() - started) * 1000)
        response.raise_for_status()
        try:
            detail = response.json()
        except ValueError:
            detail = response.text[:200] or "응답 본문 없음"
        return {"name": name, "ok": True, "message": f"HTTP {response.status_code}", "elapsed_ms": elapsed_ms, "detail": detail}
    except (httpx.HTTPError, OSError) as error:
        elapsed_ms = round((perf_counter() - started) * 1000)
        return {"name": name, "ok": False, "message": str(error), "elapsed_ms": elapsed_ms, "detail": None}


def _check_tcp(name: str, host: str, port: int, timeout: float = 3.0) -> dict:
    started = perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            elapsed_ms = round((perf_counter() - started) * 1000)
            return {"name": name, "ok": True, "message": "TCP 포트 연결 성공", "elapsed_ms": elapsed_ms, "detail": None}
    except OSError as error:
        elapsed_ms = round((perf_counter() - started) * 1000)
        return {"name": name, "ok": False, "message": str(error), "elapsed_ms": elapsed_ms, "detail": None}


def run_team_connection_checks() -> list[dict]:
    settings = get_frontend_settings()
    mcp_url = urlparse(settings.team_mcp_url)
    return [
        _check_http("Frontend", f"{settings.team_frontend_url.rstrip('/')}/_stcore/health"),
        _check_http("Backend", f"{settings.team_backend_url.rstrip('/')}/health"),
        # MCP Streamable HTTP 서버는 /health가 없을 수 있다. 포트 검사는 서버
        # 도달 여부를, 다음 Backend → MCP 검사는 실제 연동 상태를 확인한다.
        _check_tcp("MCP", mcp_url.hostname or "", mcp_url.port or 80),
        _check_http("Backend → MCP", f"{settings.team_backend_url.rstrip('/')}/api/integration/mcp"),
        _check_tcp("DB", settings.team_database_host, settings.team_database_port),
    ]


def _render_result(result: dict) -> None:
    icon = "✅" if result["ok"] else "❌"
    st.markdown(f"**{icon} {result['name']}** · {result['message']} · {result['elapsed_ms']}ms")
    if result.get("detail") is not None:
        detail = result["detail"] if isinstance(result["detail"], (dict, list)) else {"주소": result["detail"]}
        st.json(detail, expanded=False)


def render_integration_smoke_test() -> None:
    settings = get_frontend_settings()
    with st.sidebar:
        with st.expander("🔗 팀 서버 연결 테스트", expanded=False):
            st.caption("각 서버 도달 여부와 Backend → MCP 연동 상태를 확인합니다.")
            st.code(
                "\n".join(
                    (
                        f"Frontend  {settings.team_frontend_url}",
                        f"Backend   {settings.team_backend_url}",
                        f"MCP       {settings.team_mcp_url}",
                        f"DB        postgresql://{settings.team_database_user}:***@{settings.team_database_host}:{settings.team_database_port}/{settings.team_database_name}",
                    )
                ),
                language=None,
            )
            st.caption("MCP와 DB는 먼저 포트 접근을 검사합니다. Tool 호출과 SQL·인증 검사는 각각 Backend 연동 API와 Backend health에서 확인해야 합니다.")
            if st.button("전체 연결 테스트 실행", key="qa-team-connection-check", type="primary", use_container_width=True):
                with st.spinner("팀 서버 연결을 확인하고 있습니다..."):
                    st.session_state.team_connection_results = run_team_connection_checks()
            for result in st.session_state.get("team_connection_results", []):
                _render_result(result)

