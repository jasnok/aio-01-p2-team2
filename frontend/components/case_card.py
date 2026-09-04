import streamlit as st


def render_case_card(case: dict, index: int) -> None:
    with st.container(border=True):
        st.caption(f"DEMO {index} · {case['court']} · 관련도 {round(case['score'] * 100)}%")
        st.markdown(f"**{case['title']}**")
        st.caption(f"{case['case_number']} · {case['date']}")
        st.markdown(f"판결 결과: **{case['result']}**")
        st.caption("유사한 점")
        for point in case.get("points", []):
            st.markdown(f"✓ {point}")
        st.button("사례 상세 · 연동 예정", key=f"case-link-{index}-{case['case_number']}", disabled=True, use_container_width=True)
