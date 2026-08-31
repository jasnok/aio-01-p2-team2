import uuid

import streamlit as st


def initialize_session() -> None:
    if "session_id" not in st.session_state:
        st.session_state.session_id = f"web-{uuid.uuid4()}"
    if "last_result" not in st.session_state:
        st.session_state.last_result = None
    if "question_message" not in st.session_state:
        st.session_state.question_message = ""

