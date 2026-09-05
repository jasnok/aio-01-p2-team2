import streamlit as st

from frontend.services.base import LegalService


def _set_follow_up(text: str) -> None:
    st.session_state.follow_up_input = text


def _start_new_analysis() -> None:
    st.session_state.last_result = None
    st.session_state.question_message = ""
    st.session_state.follow_up_input = ""
    st.session_state.conversation_messages = []
    st.session_state.analysis_error = None


def render_follow_up_chat(result: dict, service: LegalService) -> None:
    st.markdown("### 💬 추가로 궁금한 점")
    st.caption("현재 분석 내용에 이어서 질문할 수 있습니다. Mock에서는 현재 브라우저 Session에서만 유지됩니다.")
    suggestions = result.get("follow_up_questions", [])
    if suggestions:
        columns = st.columns(min(2, len(suggestions)))
        for index, suggestion in enumerate(suggestions[:2]):
            columns[index].button(
                suggestion,
                key=f"follow-suggestion-{result['request_id']}-{index}",
                on_click=_set_follow_up,
                args=(suggestion,),
                use_container_width=True,
            )

    with st.form("follow-up-form", clear_on_submit=True):
        question = st.text_input("후속 질문", key="follow_up_input", placeholder="예: 1년 3개월 근무했다면 어떻게 확인하나요?")
        submitted = st.form_submit_button("후속 질문 분석", type="primary")
    if submitted:
        if len(question.strip()) < 5:
            st.warning("후속 질문을 5자 이상 입력해 주세요.")
            return
        combined = f"{result['question']}\n추가 정보: {question.strip()}"
        follow_result = service.analyze_case(result["agent_id"], combined)
        follow_result["parent_request_id"] = result["request_id"]
        st.session_state.conversation_messages.append({"role": "user", "content": question.strip()})
        st.session_state.conversation_messages.append({"role": "assistant", "content": follow_result["answer"]})
        st.session_state.last_result = follow_result
        st.session_state.session_history.append(follow_result)
        st.rerun()

    for message in st.session_state.conversation_messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    st.button("새 분석 시작", key="new-analysis", on_click=_start_new_analysis)
