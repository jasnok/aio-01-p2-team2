import streamlit as st

from frontend.clients.backend_client import ask_legal_question, get_backend_health


CATEGORIES = {
    "임대차·주거": "housing",
    "근로·임금": "labor",
    "중고거래·소비자 분쟁": "consumer",
}

st.set_page_config(page_title="법률 사례 검색 AI Agent", page_icon="⚖️")
st.title("법률 사례 검색 AI Agent")
st.caption("현재는 서버 연결 검증용 Mock 단계이며 법률 자문을 제공하지 않습니다.")

with st.sidebar:
    st.subheader("서버 상태")
    if st.button("Backend 연결 확인"):
        try:
            st.json(get_backend_health())
        except Exception as error:
            st.error(f"Backend 연결 실패: {error}")

category_label = st.selectbox("카테고리", list(CATEGORIES))
message = st.text_area("상황을 입력하세요", placeholder="예: 퇴직했는데 퇴직금을 받지 못했습니다.")

if st.button("관련 법률 자료 찾기", type="primary", disabled=not message.strip()):
    try:
        with st.spinner("Mock MCP 서버에서 자료를 확인하고 있습니다..."):
            result = ask_legal_question(CATEGORIES[category_label], message.strip())
        if result.get("is_mock"):
            st.warning("MOCK DATA — 실제 법률 정보가 아닌 서버 연결 검증 결과입니다.")
        st.subheader("답변")
        st.write(result["answer"])
        st.subheader("검색 자료")
        for item in result.get("laws", []) + result.get("cases", []):
            with st.container(border=True):
                st.markdown(f"**{item['title']}**")
                st.write(item["summary"])
                st.caption(f"출처: {item['source_name']} · 문서 ID: {item['document_id']}")
        st.info(result["disclaimer"])
        with st.expander("연결 Trace"):
            st.json(result.get("trace", []))
    except Exception as error:
        st.error(f"질문 처리 실패: {error}")

