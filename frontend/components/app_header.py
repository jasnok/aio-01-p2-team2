from pathlib import Path

import streamlit as st


def load_theme() -> None:
    css = (Path(__file__).parents[1] / "styles" / "theme.css").read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def render_header(show_home: bool = False) -> None:
    brand, action = st.columns([5, 1])
    with brand:
        st.markdown('<div class="lawpath-brand">⚖ LawPath</div><div class="lawpath-tagline">내 사례와 법을 연결해 드립니다</div>', unsafe_allow_html=True)
    with action:
        if show_home and st.button("⌂ 홈으로", use_container_width=True):
            from frontend.core.session import go_home

            go_home()
            st.rerun()
    st.divider()
