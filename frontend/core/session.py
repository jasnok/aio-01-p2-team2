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
        "action_checks": {},
        "notifications": ["DEMO 모드로 실행 중입니다."],
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


def reset_session() -> None:
    session_id = f"web-{uuid.uuid4()}"
    for key in list(st.session_state):
        del st.session_state[key]
    st.session_state.session_id = session_id
    initialize_session()


def restore_history_item(item: dict) -> None:
    st.session_state.selected_category = item["agent_id"]
    st.session_state.question_message = item["question"]
    st.session_state.last_result = item
    st.session_state.selected_feature = "analysis"
    st.session_state.current_page = "workspace"

