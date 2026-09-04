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
        with st.expander("판례 상세 보기"):
            st.markdown(f"**사건 개요**  \n{case['title']}")
            st.markdown(f"**판단 결과**  \n{case['result']}")
            st.markdown("**내 사례와 비교할 점**")
            for point in case.get("points", []):
                st.markdown(f"- {point}")
            st.info("관련도는 문서 유사도 예시이며 승소 가능성을 뜻하지 않습니다.")
