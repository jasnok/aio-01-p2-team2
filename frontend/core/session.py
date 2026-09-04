import uuid

import streamlit as st


def initialize_session() -> None:
    defaults = {
        "session_id": f"web-{uuid.uuid4()}",
        "current_page": "home",
        "selected_category": None,
        "selected_feature": "analysis",
        "question_message": "",
        "last_result": None,
        "law_query": "",
        "law_results": None,
        "case_query": "",
        "case_results": None,
        "session_history": [],
        "document_checks": {},
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def select_category(category: str) -> None:
    if st.session_state.selected_category != category:
        st.session_state.last_result = None
        st.session_state.law_results = None
        st.session_state.case_results = None
        st.session_state.question_message = ""
    st.session_state.selected_category = category
    st.session_state.selected_feature = "analysis"
    st.session_state.current_page = "workspace"


def go_home() -> None:
    st.session_state.current_page = "home"


def select_feature(feature: str) -> None:
    st.session_state.selected_feature = feature

