import streamlit as st

from frontend.clients import backend_client


def render_legal_terms_chat() -> None:
    st.markdown("### 법률 용어 대화")
    st.caption("사례 분석 없이도 법률 용어를 질문할 수 있습니다.")
    if st.session_state.current_user.get("role") == "GUEST":
        st.info("비회원 대화는 임시 저장되며 일정 시간이 지나면 자동 삭제됩니다. 영구 저장은 회원에게만 제공됩니다.")
    with st.form("legal-terms-chat-form", clear_on_submit=True):
        message = st.text_area("법률 용어 질문", placeholder="예: 내용증명이 무엇인가요?", max_chars=2000)
        save = st.checkbox("이 대화를 저장하기", disabled=st.session_state.current_user.get("role") == "GUEST")
        submitted = st.form_submit_button("질문하기", type="primary")
    if submitted:
        if not message.strip():
            st.warning("질문을 입력해 주세요.")
            return
        if st.session_state.current_user.get("role") == "GUEST" and save:
            st.info("대화를 저장하려면 먼저 로그인해 주세요.")
            return
        try:
            payload = backend_client.chat_legal_terms(
                st.session_state.auth_token,
                f"guest-{st.session_state.session_id}",
                message.strip(),
                save_selected=save,
            )
            st.session_state.legal_terms_last = payload
        except backend_client.BackendClientError as error:
            st.error(error.user_message)
    payload = st.session_state.get("legal_terms_last")
    if payload:
        st.markdown("#### 답변")
        st.write(payload.get("answer") or payload.get("message") or payload.get("content") or "답변을 확인할 수 없습니다.")
