import uuid

import streamlit as st

from copy import deepcopy
from frontend.data.mock_community import MOCK_FAQ_ARTICLES, ROLE_USERS, build_mock_questions
from frontend.services.mock_auth_service import build_demo_accounts
from frontend.services.mock_notification_service import create_notification


def initialize_session() -> None:
    session_id = st.session_state.get("session_id", f"web-{uuid.uuid4()}")
    guest_user = deepcopy(ROLE_USERS["GUEST"])
    guest_user["id"] = f"guest-{session_id}"
    defaults = {
        "session_id": session_id,
        "auth_token": None,
        "auth_expires_in": None,
        "current_page": "home",
        "selected_category": None,
        "selected_feature": "analysis",
        "question_message": "",
        "analysis_draft": "",
        "last_result": None,
        "law_query": "",
        "law_results": None,
        "case_query": "",
        "case_results": None,
        "consultation_query": "",
        "consultation_results": None,
        "search_errors": {},
        "session_history": [],
        "document_checks": {},
        "action_checks": {},
        "notifications": [
            create_notification(
                "DEMO_MODE",
                "DEMO 모드로 실행 중입니다.",
                "현재 결과와 알림은 화면 확인용이며 실제 법률정보가 아닙니다.",
                severity="info",
            )
        ],
        "presentation_step": 1,
        "mock_role": "GUEST",
        "current_user": guest_user,
        "faq_articles": deepcopy(MOCK_FAQ_ARTICLES),
        "public_questions": build_mock_questions(),
        "question_page": 1,
        "question_page_size": 10,
        "question_create_flash": None,
        "reset_question_form": False,
        "question_edit_id": None,
        "admin_faq_edit_id": None,
        "history_filter": "all",
        "analysis_in_progress": False,
        "agent_run_id": None,
        "agent_run_status": None,
        "analysis_error": None,
        "mock_scenario": "success",
        "conversation_messages": [],
        "evaluation_results": [],
        "mock_accounts": build_demo_accounts(),
        "auth_message": None,
        "unlocked_question_ids": set(),
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    if st.session_state.selected_feature not in {"analysis", "terms", "faq", "history", "admin_faq"}:
        st.session_state.selected_feature = "analysis"


def select_category(category: str) -> None:
    if st.session_state.selected_category != category:
        st.session_state.last_result = None
        st.session_state.law_results = None
        st.session_state.case_results = None
        st.session_state.consultation_results = None
        st.session_state.law_query = ""
        st.session_state.case_query = ""
        st.session_state.consultation_query = ""
        st.session_state.search_errors = {}
        st.session_state.question_message = ""
        st.session_state.analysis_draft = ""
        st.session_state.conversation_messages = []
        st.session_state.analysis_error = None
    st.session_state.selected_category = category
    st.session_state.selected_feature = "analysis"
    st.session_state.current_page = "workspace"


def go_home() -> None:
    st.session_state.current_page = "home"


def select_feature(feature: str) -> None:
    if st.session_state.selected_feature == "analysis":
        st.session_state.analysis_draft = st.session_state.get("question_message", "")
    if feature == "analysis" and st.session_state.selected_feature != "analysis":
        st.session_state.question_message = st.session_state.get("analysis_draft", "")
    st.session_state.selected_feature = feature


def set_mock_role(role: str) -> None:
    if role not in ROLE_USERS:
        raise ValueError("지원하지 않는 Mock 역할입니다.")
    st.session_state.mock_role = role
    user = deepcopy(ROLE_USERS[role])
    if role == "GUEST":
        user["id"] = f"guest-{st.session_state.session_id}"
    st.session_state.current_user = user
    st.session_state.question_edit_id = None
    st.session_state.unlocked_question_ids = set()


def reset_session() -> None:
    session_id = f"web-{uuid.uuid4()}"
    for key in list(st.session_state):
        del st.session_state[key]
    st.session_state.session_id = session_id
    initialize_session()


def restore_history_item(item: dict) -> None:
    select_category(item["agent_id"])
    st.session_state.question_message = item["question"]
    st.session_state.analysis_draft = item["question"]
    st.session_state.last_result = item
    st.session_state.selected_feature = "analysis"
    st.session_state.current_page = "workspace"

