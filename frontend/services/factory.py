import streamlit as st

from frontend.core.config import get_frontend_settings
from frontend.services.base import LegalService
from frontend.services.api_legal_service import ApiLegalService
from frontend.services.mock_legal_service import MockLegalService


def get_legal_service() -> LegalService:
    mode = get_frontend_settings().frontend_data_mode.lower()
    if mode == "mock":
        return MockLegalService()
    if mode == "api":
        return ApiLegalService(st.session_state.current_user["id"])
    raise ValueError("FRONTEND_DATA_MODE는 mock 또는 api만 사용할 수 있습니다.")
