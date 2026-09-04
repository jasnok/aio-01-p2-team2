import streamlit as st

from frontend.core.session import select_category
from frontend.services.base import LegalService


PRESENTATION_QUESTION = "월세 계약이 끝났는데 집주인이 보증금을 돌려주지 않고 있습니다. 내용증명을 보냈지만 답이 없습니다."


def _prepare_demo(service: LegalService) -> None:
    select_category("housing")
    result = service.analyze_case("housing", PRESENTATION_QUESTION)
    st.session_state.question_message = PRESENTATION_QUESTION
    st.session_state.last_result = result
    st.session_state.session_history = [result]
    st.session_state.presentation_step = 2


def render_presentation_panel(service: LegalService) -> None:
    with st.sidebar:
        with st.container(border=True):
            st.markdown("#### 🎬 발표용 데모")
            st.caption("대표 시나리오를 한 번에 준비합니다.")
            st.button(
                "임대차 데모 불러오기",
                key="presentation-load",
                on_click=_prepare_demo,
                args=(service,),
                type="primary",
                use_container_width=True,
            )
            st.caption("① 분야 선택 → ② 사례 분석 → ③ 상세 확인 → ④ 결과 저장")
