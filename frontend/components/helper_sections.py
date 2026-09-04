import streamlit as st

from frontend.data.mock_catalog import MOCK_CATALOG


def render_helper_feature(category: str, feature: str) -> None:
    data = MOCK_CATALOG[category]
    st.caption("후순위 기능 · 현재는 화면과 세션 동작만 제공합니다.")
    if feature == "terms":
        st.markdown("### ▣ 쉬운 법률 용어")
        for term, description in data["terms"]:
            with st.container(border=True):
                st.markdown(f"**{term}**")
                st.write(description)
    elif feature == "documents":
        st.markdown("### □ 필요 서류")
        for index, document in enumerate(data["documents"]):
            key = f"doc-{category}-{index}"
            st.checkbox(document, key=key)
        st.info("체크 상태는 현재 브라우저 세션에서만 유지됩니다.")
    elif feature == "actions":
        st.markdown("### ◷ 다음 행동")
        for index, action in enumerate(data["actions"], 1):
            st.markdown(f"**{index}.** {action}")
    elif feature == "faq":
        st.markdown("### ? FAQ")
        for question, answer in data["faqs"]:
            with st.expander(question):
                st.write(answer)
    elif feature == "history":
        st.markdown("### ↶ 질의 이력")
        history = st.session_state.session_history
        if not history:
            st.markdown('<div class="coming-soon">아직 분석한 사례가 없습니다.</div>', unsafe_allow_html=True)
        for item in reversed(history):
            with st.container(border=True):
                st.caption("현재 세션에만 저장됨")
                st.markdown(f"**{item['question']}**")
                st.write(item["question_summary"])
