from dataclasses import dataclass

import streamlit as st

from frontend.components.input_checklist import render_input_checklist


DEMO_QUESTIONS = {
    "housing": "주택 임대차 계약이 끝났는데 임대인이 보증금을 돌려주지 않습니다. 어떤 법 조문을 확인해야 하나요?",
    "labor": "퇴직했는데 회사가 퇴직금을 지급하지 않습니다. 퇴직금 지급 기한과 관련 법 조문을 알려주세요.",
    "consumer": "신용카드 일시불 결제 후 할부로 전환했는데 물건이 배송되지 않았습니다. 카드사에 할부항변권을 행사할 수 있나요?",
}


@dataclass(frozen=True)
class QuestionSubmission:
    category: str
    message: str
    save_selected: bool = False


def _apply_demo_question(category: str) -> None:
    st.session_state.question_message = DEMO_QUESTIONS[category]


def render_question_form(category: str) -> QuestionSubmission | None:
    st.markdown("### ✦ 내 사례 분석")
    st.caption("언제, 누구와, 어떤 일이 있었는지 자유롭게 입력해 주세요.")
    st.button("대표 질문 불러오기", on_click=_apply_demo_question, args=(category,))

    message = st.text_area(
        "법률 문제 상황",
        key="question_message",
        height=150,
        max_chars=2000,
        placeholder="언제, 누구와, 어떤 일이 있었는지 구체적으로 작성하면 검색 정확도가 높아집니다.",
    )
    render_input_checklist(category, message, st.session_state.get("last_result"))
    from frontend.core.config import get_frontend_settings
    if get_frontend_settings().frontend_data_mode.lower() == "api":
        pending = st.session_state.get("sse_pending")
        if pending and not pending.get("finished") and pending.get("identity", (None, None, None))[1:] == (category, message.strip()):
            st.caption("다시 시도하면 기존 분석과 처음 선택한 저장 여부를 유지합니다.")
    submitted = st.button(
        "처리 중입니다..." if st.session_state.analysis_in_progress else "✦ 사례 분석하기",
        type="primary",
        use_container_width=True,
        disabled=st.session_state.analysis_in_progress,
    )

    if not submitted:
        return None
    if len(message.strip()) < 5:
        st.warning("질문을 5자 이상 입력해 주세요.")
        return None
    # New analyses do not inherit a storage selection from an older screen.
    # Saving an existing result requires a backend post-analysis save endpoint.
    return QuestionSubmission(category=category, message=message.strip(), save_selected=False)

