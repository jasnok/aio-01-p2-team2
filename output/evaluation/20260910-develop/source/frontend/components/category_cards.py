import streamlit as st

from frontend.core.session import select_category
from frontend.data.categories import CATEGORIES


def render_category_cards() -> None:
    columns = st.columns(3, gap="large")
    for column, category in zip(columns, CATEGORIES.values(), strict=True):
        with column:
            with st.container(border=True):
                st.markdown(f"### {category.icon} {category.name}")
                st.caption(category.description)
                for example in category.examples:
                    st.markdown(f"- {example}")
                if st.button("선택하기 →", key=f"category-{category.code}", type="primary", use_container_width=True):
                    select_category(category.code)
                    st.rerun()
