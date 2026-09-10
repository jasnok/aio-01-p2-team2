import streamlit as st

from frontend.clients import backend_client
from frontend.core.config import get_frontend_settings


def reset_terms_chat():
    st.session_state.update(terms_messages=[], terms_conversation_id=None,
                            terms_saved=False, terms_reply={}, terms_input="",
                            terms_save=False, terms_save_login_notice=False)


def start_new_terms_chat():
    reset_terms_chat()
    st.session_state.terms_reset_notice = True


def render_legal_terms_chat(result: dict) -> None:
    st.markdown("### 법률 용어 대화")
    st.caption("방금 분석한 사례의 법률 용어나 표현을 쉽게 풀어드립니다.")
    identity = (st.session_state.auth_token, result.get("request_id"), result.get("question"))
    if st.session_state.get("terms_identity") != identity:
        reset_terms_chat()
        st.session_state.terms_identity = identity
        st.session_state.terms_messages = []
        st.session_state.terms_conversation_id = None
        st.session_state.terms_reset_notice = False
    if get_frontend_settings().frontend_data_mode.lower() != "api":
        st.info("법률 용어 대화는 실제 서버 연결 모드에서 사용할 수 있습니다.")
        return
    token = st.session_state.auth_token
    st.button("새 대화 시작", key="terms-new", on_click=start_new_terms_chat)
    if st.session_state.pop("terms_reset_notice", False):
        st.info("새 대화를 시작했습니다. 현재 사례 분석을 참고해 질문할 수 있습니다.")
    with st.form("legal-terms-chat-form", clear_on_submit=False):
        message = st.text_area("분석 내용에서 궁금한 법률 용어", key="terms_input", placeholder="예: 이 사례에서 할부항변권은 무엇인가요?", max_chars=400)
        submitted = st.form_submit_button("질문하기", type="primary")
    if submitted:
        if len(message.strip()) < 2:
            st.warning("질문을 2자 이상 입력해 주세요.")
            return
        try:
            payload = backend_client.chat_legal_terms(
                st.session_state.auth_token,
                f"guest-{st.session_state.session_id}",
                build_context_message(result, message.strip(), st.session_state.terms_messages),
                save_selected=False,
                conversation_id=st.session_state.terms_conversation_id,
            )
            answer = payload.get("answer")
            if not isinstance(answer, str) or not answer.strip():
                raise backend_client.BackendClientError("대화 응답 형식을 확인할 수 없습니다.")
            st.session_state.terms_conversation_id = payload.get("conversation_id")
            st.session_state.terms_reply = payload
            st.session_state.terms_messages.extend([{"role": "user", "content": message.strip()}, {"role": "assistant", "content": answer,
                "request_id": payload.get("request_id"), "saved": payload.get("saved", False)}])
            if payload.get("saved") is True:
                st.session_state.terms_saved = True
                st.success("대화가 저장되었습니다.")
        except backend_client.BackendClientError as error:
            st.error(error.user_message)
    reply = st.session_state.get("terms_reply", {})
    if reply.get("storage") == "guest_temporary":
        st.caption("이 대화는 임시 보관되며 서버 보관 기간이 지나면 삭제됩니다.")
    if reply.get("expires_at"):
        st.caption(f"만료 시각: {reply['expires_at']}")
    for entry in st.session_state.terms_messages:
        with st.chat_message(entry["role"]):
            st.text(entry["content"])
            if entry["role"] == "assistant" and token:
                from frontend.components.result_save import render_result_save
                render_result_save(entry, kind="legal_terms", result_id=entry.get("request_id"))


def build_context_message(result, question, messages):
    if not 2 <= len(question) <= 400:
        raise ValueError("질문은 2~400자로 입력해 주세요.")
    context = ("이전 분석을 참고해 현재 질문의 법률 용어를 쉽게 설명해주세요.\n"
               f"원래 질문: {result.get('question', '')[:140]}\n"
               f"분석 요약: {result.get('question_summary', '')[:140]}\n"
               f"답변 발췌: {result.get('answer', '')[:120]}\n")
    for entry in messages[-2:]:
        context += f"{entry['role']}: {entry['content'][:40]}\n"
    suffix = "현재 질문: " + question
    return context[:1000-len(suffix)] + suffix
