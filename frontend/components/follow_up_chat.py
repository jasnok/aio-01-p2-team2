import streamlit as st

from frontend.services.base import LegalService
from frontend.core.config import get_frontend_settings
from frontend.components.stream_analysis import analyze_with_stream


def _set_follow_up(text: str) -> None:
    st.session_state.follow_up_input = text


def _start_new_analysis() -> None:
    st.session_state.last_result = None
    st.session_state.question_message = ""
    st.session_state.analysis_draft = ""
    st.session_state.follow_up_input = ""
    st.session_state.conversation_messages = []
    st.session_state.analysis_error = None
    st.session_state.pop("sse_pending", None)


def render_follow_up_chat(result: dict, service: LegalService) -> None:
    needs_input = result.get("result_state") == "needs_clarification"
    st.markdown("### 💬 추가 정보 입력" if needs_input else "### 💬 추가로 궁금한 점")
    st.caption("현재 질문에 추가 정보를 이어서 분석합니다. DB의 이전 대화를 조회하는 기능은 아직 연결되지 않았습니다.")
    suggestions = result.get("follow_up_questions", [])
    if suggestions and not needs_input:
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
        question = st.text_input("추가 정보" if needs_input else "후속 질문", key="follow_up_input", placeholder="예: 1년 3개월 근무했습니다.")
        submitted = st.form_submit_button("추가 정보로 다시 분석" if needs_input else "후속 질문 분석", type="primary")
    if submitted:
        if len(question.strip()) < 5:
            st.warning("후속 질문을 5자 이상 입력해 주세요.")
            return
        combined = f"{result['question']}\n추가 정보: {question.strip()}"
        if len(combined) > 2000:
            st.warning("원래 질문과 추가 정보를 합쳐 2000자 이내로 입력해 주세요.")
            return
        try:
            settings = get_frontend_settings()
            if settings.frontend_data_mode.lower() == "api" and settings.frontend_sse_enabled:
                follow_result = analyze_with_stream(result["agent_id"], combined)
            else:
                follow_result = service.analyze_case(result["agent_id"], combined)
        except ValueError as error:
            st.error(str(error))
            return
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
