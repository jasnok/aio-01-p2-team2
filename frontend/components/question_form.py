from dataclasses import dataclass

import streamlit as st


CATEGORIES = {
    "임대차·주거": "housing",
    "근로·임금": "labor",
    "중고거래·소비자 분쟁": "consumer",
}

DEMO_QUESTIONS = {
    "임대차": ("임대차·주거", "월세 계약이 끝났는데 집주인이 보증금을 돌려주지 않습니다."),
    "근로": ("근로·임금", "퇴직했는데 퇴직금을 받지 못했습니다."),
    "중고거래": ("중고거래·소비자 분쟁", "중고거래로 돈을 보냈는데 판매자가 물건을 보내지 않습니다."),
}


@dataclass(frozen=True)
class QuestionSubmission:
    category: str
    message: str


def _apply_demo_question(label: str) -> None:
    category, message = DEMO_QUESTIONS[label]
    st.session_state.category_label = category
    st.session_state.question_message = message


def render_question_form() -> QuestionSubmission | None:
    st.subheader("상황 입력")
    st.write("대표 질문을 선택하거나 본인의 상황을 자연어로 작성하세요.")

    demo_columns = st.columns(3)
    for column, label in zip(demo_columns, DEMO_QUESTIONS, strict=True):
        column.button(label, use_container_width=True, on_click=_apply_demo_question, args=(label,))

    with st.form("legal-question-form"):
        category_label = st.selectbox("카테고리", list(CATEGORIES), key="category_label")
        message = st.text_area(
            "법률 문제 상황",
            key="question_message",
            height=150,
            max_chars=2000,
            placeholder="언제, 누구와, 어떤 일이 있었는지 구체적으로 작성하면 검색 정확도가 높아집니다.",
        )
        submitted = st.form_submit_button("관련 법률 자료 찾기", type="primary", use_container_width=True)

    if not submitted:
        return None
    if len(message.strip()) < 5:
        st.warning("질문을 5자 이상 입력해 주세요.")
        return None
    return QuestionSubmission(category=CATEGORIES[category_label], message=message.strip())

