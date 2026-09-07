import uuid

import streamlit as st

from copy import deepcopy
from frontend.data.mock_community import MOCK_FAQ_ARTICLES, ROLE_USERS, build_mock_questions


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
        "presentation_step": 1,
        "mock_role": "GUEST",
        "current_user": deepcopy(ROLE_USERS["GUEST"]),
        "faq_articles": deepcopy(MOCK_FAQ_ARTICLES),
        "public_questions": build_mock_questions(),
        "question_page": 1,
        "question_page_size": 10,
        "question_edit_id": None,
        "admin_faq_edit_id": None,
        "history_filter": "all",
        "analysis_in_progress": False,
        "analysis_error": None,
        "mock_scenario": "success",
        "conversation_messages": [],
        "evaluation_results": [],
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
        st.session_state.conversation_messages = []
        st.session_state.analysis_error = None
    st.session_state.selected_category = category
    st.session_state.selected_feature = "analysis"
    st.session_state.current_page = "workspace"


def go_home() -> None:
    st.session_state.current_page = "home"


def select_feature(feature: str) -> None:
    st.session_state.selected_feature = feature


def set_mock_role(role: str) -> None:
    if role not in ROLE_USERS:
        raise ValueError("지원하지 않는 Mock 역할입니다.")
    st.session_state.mock_role = role
    st.session_state.current_user = deepcopy(ROLE_USERS[role])
    st.session_state.question_edit_id = None


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

