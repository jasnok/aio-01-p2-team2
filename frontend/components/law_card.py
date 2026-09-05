import streamlit as st


def render_law_card(law: dict, index: int) -> None:
    with st.container(border=True):
        st.caption(f"근거 L{index} · 관련 법령")
        st.markdown(f"**{law['title']}**")
        st.caption(law.get("article", "조문 정보 없음"))
        st.write(law.get("summary", "요약이 없습니다."))
        with st.expander("법령 상세 보기"):
            st.write(law.get("detail", law.get("summary", "상세 설명이 없습니다.")))
            st.caption(f"출처: {law.get('source', '공식 출처 연동 예정')}")
            st.caption("공식 원문 URL은 Backend 연동 후 제공됩니다.")
            st.info("현재는 DEMO 설명입니다. 실제 서비스에서는 공식 원문과 시행일을 함께 표시합니다.")
