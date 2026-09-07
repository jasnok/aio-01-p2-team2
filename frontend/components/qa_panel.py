import streamlit as st

from frontend.core.session import reset_session, select_category, set_mock_role
from frontend.data.mock_catalog import MOCK_CATALOG
from frontend.services.base import LegalService
from frontend.core.workflow import MOCK_SCENARIOS
from frontend.components.evaluation_panel import render_evaluation_panel
from frontend.services.mock_notification_service import add_notification


def _load_scenario(category: str, service: LegalService) -> None:
    select_category(category)
    question = {
        "housing": "계약이 끝났는데 보증금을 받지 못했습니다.",
        "labor": "퇴직했는데 퇴직금을 받지 못했습니다.",
        "consumer": "돈을 보냈는데 물건을 받지 못했습니다.",
    }[category]
    result = service.analyze_case(category, question)
    st.session_state.question_message = question
    st.session_state.last_result = result
    st.session_state.session_history.append(result)


def _load_empty_state() -> None:
    st.session_state.selected_feature = "laws"
    st.session_state.law_results = []


def _load_long_text() -> None:
    st.session_state.selected_feature = "analysis"
    st.session_state.question_message = "계약과 반환 요청에 관한 상세한 사실관계를 확인하기 위한 긴 입력 예시입니다. " * 10


def _add_notification_scenario(kind: str) -> None:
    scenarios = {
        "answered": (
            "QUESTION_ANSWERED",
            "질문에 답변이 등록되었습니다.",
            "FAQ에서 작성한 질문의 DEMO 답변을 확인해 주세요.",
            "success",
            "question",
        ),
        "expiring": (
            "HISTORY_EXPIRING",
            "비회원 질의 이력이 곧 만료됩니다.",
            "DEMO 이력이 24시간 후 만료되는 상황을 확인합니다.",
            "warning",
            "history",
        ),
        "system_error": (
            "SYSTEM_ERROR",
            "팀 서버 연결을 확인해 주세요.",
            "Backend·MCP·DB 중 한 구간의 연결 실패를 가정한 관리자용 DEMO 알림입니다.",
            "error",
            None,
        ),
    }
    notification_type, title, message, severity, target_type = scenarios[kind]
    add_notification(
        st.session_state.notifications,
        notification_type,
        title,
        message,
        severity=severity,
        target_type=target_type,
        category=st.session_state.selected_category,
    )


def render_qa_panel(service: LegalService) -> None:
    with st.sidebar:
        with st.expander("🧪 QA 빠른 테스트"):
            st.caption("개발용 화면 상태를 한 번에 불러옵니다.")
            st.selectbox(
                "다음 분석 결과",
                options=list(MOCK_SCENARIOS),
                format_func=MOCK_SCENARIOS.get,
                key="mock_scenario",
                help="사례 분석 버튼을 누르면 선택한 상태를 Mock으로 재현합니다.",
            )
            st.caption("역할 전환 · 실제 인증 아님")
            role_columns = st.columns(3)
            for column, role, label in zip(role_columns, ("GUEST", "USER", "ADMIN"), ("비회원", "회원", "관리자"), strict=True):
                column.button(label, key=f"qa-role-{role.lower()}", on_click=set_mock_role, args=(role,), use_container_width=True)
            for category in MOCK_CATALOG:
                label = {"housing": "임대차 결과", "labor": "근로 결과", "consumer": "소비자 결과"}[category]
                st.button(label, key=f"qa-{category}", on_click=_load_scenario, args=(category, service), use_container_width=True)
            st.button("결과 없음", key="qa-empty", on_click=_load_empty_state, use_container_width=True)
            st.button("긴 입력", key="qa-long", on_click=_load_long_text, use_container_width=True)
            st.caption("Mock 알림 생성")
            notification_columns = st.columns(3)
            notification_columns[0].button("답변 완료", key="qa-notification-answered", on_click=_add_notification_scenario, args=("answered",), use_container_width=True)
            notification_columns[1].button("만료 예정", key="qa-notification-expiring", on_click=_add_notification_scenario, args=("expiring",), use_container_width=True)
            notification_columns[2].button("연결 오류", key="qa-notification-error", on_click=_add_notification_scenario, args=("system_error",), use_container_width=True)
            st.button("전체 세션 초기화", key="qa-reset", on_click=reset_session, use_container_width=True)
            st.divider()
            render_evaluation_panel(service)
