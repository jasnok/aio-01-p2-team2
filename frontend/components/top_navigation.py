import streamlit as st

from frontend.core.session import select_feature
from frontend.data.categories import get_category

FEATURES = [
    ("analysis", "내 사례 분석"),
    ("terms", "법률 용어 대화"),
    ("faq", "FAQ"),
    ("history", "질의 이력"),
]


def render_top_navigation(category_code: str) -> None:
    category = get_category(category_code)
    st.caption(f"{category.icon} {category.name} · {category.description}")
    for column, (code, label) in zip(st.columns(len(FEATURES)), FEATURES, strict=True):
        selected = st.session_state.selected_feature == code
        with column:
            st.button(label, key=f"nav-{code}", type="primary" if selected else "secondary",
                      use_container_width=True, on_click=select_feature, args=(code,))
