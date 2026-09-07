import streamlit as st

from frontend.core.session import select_feature
from frontend.data.categories import get_category

FEATURES = [
    ("analysis", "✎", "내 사례 분석", True),
    ("laws", "⌕", "법 검색", True),
    ("cases", "⚖", "실제 사례", True),
    ("terms", "▣", "쉬운 법률 용어", True),
    ("documents", "□", "필요 서류", True),
    ("actions", "◷", "다음 행동", True),
    ("faq", "?", "FAQ", True),
    ("history", "↶", "질의 이력", True),
]


def render_sidebar(category_code: str) -> None:
    category = get_category(category_code)
    with st.sidebar:
        st.markdown(f"## {category.icon} {category.name}")
        st.caption(category.description)
        st.divider()
        for code, icon, label, active in FEATURES:
            suffix = "" if active else " · 준비 중"
            button_type = "primary" if st.session_state.selected_feature == code else "secondary"
            if st.button(f"{icon}  {label}{suffix}", key=f"nav-{code}", type=button_type, use_container_width=True):
                select_feature(code)
                st.rerun()
        if st.session_state.current_user["role"] == "ADMIN":
            button_type = "primary" if st.session_state.selected_feature == "admin_faq" else "secondary"
            if st.button("🛠  FAQ 관리 · MOCK", key="nav-admin-faq", type=button_type, use_container_width=True):
                select_feature("admin_faq")
                st.rerun()
        st.divider()
        st.caption("DEMO MODE · Backend 연결 없음")
        st.info("화면의 법령과 사례는 UI 확인용 예시이며 실제 법률정보가 아닙니다.")
