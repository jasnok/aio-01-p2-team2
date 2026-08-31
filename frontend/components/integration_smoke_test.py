import streamlit as st

from frontend.clients.backend_client import (
    BackendClientError,
    get_mcp_integration_status,
    search_food_mock,
)


def render_integration_smoke_test() -> None:
    with st.expander("Frontend → Backend → MCP 확인", expanded=False):
        st.caption("병훈 Food MCP의 교육용 Mock 데이터로 서버 연결만 확인합니다.")

        if st.button("MCP Tool 목록 확인", use_container_width=True):
            try:
                status = get_mcp_integration_status()
                st.success("Backend → MCP 연결 성공")
                st.write(f"Server: `{status['server']}`")
                for tool in status.get("tools", []):
                    st.markdown(f"- `{tool}`")
            except BackendClientError as error:
                st.error(error.user_message)
                if error.code:
                    st.caption(f"오류 코드: {error.code}")

        if st.button("서울 한식 Mock 검색", type="primary", use_container_width=True):
            try:
                result = search_food_mock()
                st.success("Frontend → Backend → MCP 연결 성공")
                st.caption(" → ".join(result.get("path", [])))
                for item in result.get("items", []):
                    with st.container(border=True):
                        st.markdown(f"**{item['name']}**")
                        st.write(f"{item['region']} · {item['food_category']} · {item['price']:,}원")
                        st.caption(f"ID: {item['restaurant_id']}")
                st.caption(f"Source: {result.get('source', 'unknown')}")
            except BackendClientError as error:
                st.error(error.user_message)
                if error.code:
                    st.caption(f"오류 코드: {error.code}")

