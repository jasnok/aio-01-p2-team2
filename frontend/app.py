import streamlit as st

from frontend.clients.backend_client import BackendClientError, ask_legal_question
from frontend.components.answer_view import render_answer
from frontend.components.connection_status import render_connection_status
from frontend.components.question_form import render_question_form
from frontend.core.session import initialize_session


st.set_page_config(
    page_title="법률 사례 검색 AI Agent",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)
initialize_session()

st.title("⚖️ 법률 사례 검색 AI Agent")
st.caption("공식 법률 근거와 유사 사례를 찾아 이해하기 쉽게 정리합니다.")
st.info("이 서비스는 법률 자문이나 판결 예측을 제공하지 않습니다. 중요한 결정 전에는 전문가와 상담하세요.")

with st.sidebar:
    render_connection_status()
    st.divider()
    st.subheader("지원 범위")
    st.write("임대차·주거 · 근로·임금 · 중고거래·소비자 분쟁")

submission = render_question_form()
if submission:
    try:
        with st.status("법률 자료를 검색하고 있습니다...", expanded=True) as status:
            st.write("질문과 카테고리를 확인했습니다.")
            st.write("Backend에 법률 자료 검색을 요청합니다.")
            result = ask_legal_question(
                category=submission.category,
                message=submission.message,
                session_id=st.session_state.session_id,
            )
            status.update(label="답변 준비가 완료되었습니다.", state="complete", expanded=False)
        st.session_state.last_result = result
    except BackendClientError as error:
        st.session_state.last_result = None
        st.error(error.user_message)
        if error.code:
            st.caption(f"오류 코드: {error.code}")

if st.session_state.last_result:
    render_answer(st.session_state.last_result)
