import streamlit as st


def render_law_card(law: dict, index: int) -> None:
    with st.container(border=True):
        st.caption(f"관련 법령 {index}")
        st.markdown(f"**{law['title']}**")
        st.caption(law.get("article", "조문 정보 없음"))
        st.write(law.get("summary", "요약이 없습니다."))
        st.button("원문 보기 · 연동 예정", key=f"law-link-{index}-{law['title']}", disabled=True, use_container_width=True)
