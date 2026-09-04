from dataclasses import dataclass

import streamlit as st


DEMO_QUESTIONS = {
    "housing": "월세 계약이 끝났는데 집주인이 보증금을 돌려주지 않습니다.",
    "labor": "퇴직했는데 퇴직금을 받지 못했습니다.",
    "consumer": "중고거래로 돈을 보냈는데 판매자가 물건을 보내지 않습니다.",
}


@dataclass(frozen=True)
class QuestionSubmission:
    category: str
    message: str


def _apply_demo_question(category: str) -> None:
    st.session_state.question_message = DEMO_QUESTIONS[category]


def render_question_form(category: str) -> QuestionSubmission | None:
    st.markdown("### ✦ 내 사례 분석")
    st.caption("언제, 누구와, 어떤 일이 있었는지 자유롭게 입력해 주세요.")
    st.button("대표 질문 불러오기", on_click=_apply_demo_question, args=(category,))

    with st.form("legal-question-form"):
        message = st.text_area(
            "법률 문제 상황",
            key="question_message",
            height=150,
            max_chars=2000,
            placeholder="언제, 누구와, 어떤 일이 있었는지 구체적으로 작성하면 검색 정확도가 높아집니다.",
        )
        submitted = st.form_submit_button("✦ 사례 분석하기", type="primary", use_container_width=True)

    if not submitted:
        return None
    if len(message.strip()) < 5:
        st.warning("질문을 5자 이상 입력해 주세요.")
        return None
    return QuestionSubmission(category=category, message=message.strip())

