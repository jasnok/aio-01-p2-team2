import streamlit as st

from frontend.components.analysis_summary import render_analysis_summary
from frontend.components.answer_view import render_analysis_result
from frontend.components.app_header import load_theme, render_header
from frontend.components.category_cards import render_category_cards
from frontend.components.helper_sections import render_helper_feature
from frontend.components.integration_smoke_test import render_integration_smoke_test
from frontend.components.question_form import render_question_form
from frontend.components.presentation_panel import render_presentation_panel
from frontend.components.admin_faq import render_admin_faq
from frontend.components.top_navigation import render_top_navigation
from frontend.core.session import initialize_session
from frontend.data.categories import get_category
from frontend.core.config import get_frontend_settings
from frontend.services.factory import get_legal_service
from frontend.core.workflow import MockScenarioError
from frontend.components.analysis_progress import render_analysis_error, render_analysis_progress
from frontend.components.follow_up_chat import render_follow_up_chat
from frontend.services.mock_notification_service import add_notification
from frontend.components.stream_analysis import analyze_with_stream


st.set_page_config(page_title="LawPath", page_icon="⚖️", layout="wide", initial_sidebar_state="collapsed")
initialize_session()
load_theme()


def render_home() -> None:
    render_header()
    st.markdown('<div class="page-kicker">LIFE LEGAL GUIDE</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-title">어떤 법률 문제를 확인하고 싶으신가요?</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-description">생활 속 법률 분야를 선택하면 사례 분석을 시작할 수 있습니다.</div>', unsafe_allow_html=True)
    render_category_cards()
    st.info("이 서비스는 법률 자문이나 판결 예측을 제공하지 않습니다. 현재 화면은 DEMO 데이터로 동작합니다.")


def render_workspace() -> None:
    category_code = st.session_state.selected_category
    if not category_code:
        st.session_state.current_page = "home"
        st.rerun()
    category = get_category(category_code)
    service = get_legal_service()
    settings = get_frontend_settings()
    render_header(show_home=True)
    render_top_navigation(category_code)
    if settings.frontend_connection_check_enabled:
        render_integration_smoke_test()
    if settings.frontend_presentation_mode:
        render_presentation_panel(service)
    labels = {"analysis": "내 사례 분석", "laws": "법 검색", "consultations": "실제 사례 검색", "cases": "판례 검색", "faq": "FAQ", "history": "질의 이력", "admin_faq": "FAQ 관리"}
    st.caption(f"{category.name}  ›  {labels[st.session_state.selected_feature]}")

    feature = st.session_state.selected_feature
    if feature == "analysis":
        input_column, summary_column = st.columns([1, 1.35], gap="large")
        with input_column:
            submission = render_question_form(category_code)
        if submission:
            st.session_state.analysis_in_progress = True
            st.session_state.analysis_error = None
            refresh_after_notification = False
            try:
                st.session_state.last_result = None
                with st.status("사례를 분석하고 있습니다.", expanded=True) as progress:
                    try:
                        if settings.frontend_data_mode.lower() == "api" and settings.frontend_sse_enabled:
                            result = analyze_with_stream(category_code, submission.message)
                        else:
                            result = service.analyze_case(
                                category_code,
                                submission.message,
                                scenario=st.session_state.mock_scenario,
                            )
                    except Exception:
                        progress.update(label="분석을 완료하지 못했습니다.", state="error")
                        raise
                    needs_input = result.get("result_state") == "needs_clarification"
                    progress.update(label="추가 정보가 필요합니다." if needs_input else "분석 요청 처리가 완료되었습니다.", state="complete", expanded=needs_input)
                st.session_state.last_result = result
                st.session_state.session_history.append(result)
                result_state = result.get("result_state", "completed")
                if result_state == "needs_clarification":
                    st.info("아래 추가 질문에 답해 주세요.")
                elif result_state == "no_evidence":
                    add_notification(
                        st.session_state.notifications,
                        "ANALYSIS_NO_EVIDENCE",
                        "공식 근거가 부족합니다.",
                        "단정적인 답변을 생성하지 않았습니다. 질문을 구체화해 다시 시도해 주세요.",
                        severity="warning",
                        target_type="analysis",
                        target_id=result["request_id"],
                        category=category_code,
                    )
                elif result_state == "no_results":
                    add_notification(
                        st.session_state.notifications,
                        "ANALYSIS_NO_RESULTS",
                        "검색 결과가 없습니다.",
                        "질문에 날짜, 상대방과 요청 내용을 추가해 보세요.",
                        severity="warning",
                        target_type="analysis",
                        target_id=result["request_id"],
                        category=category_code,
                    )
                else:
                    add_notification(
                        st.session_state.notifications,
                        "ANALYSIS_COMPLETED",
                        "사례 분석이 완료되었습니다.",
                        "상황 요약과 관련 법령·판례를 확인해 주세요.",
                        severity="success",
                        target_type="analysis",
                        target_id=result["request_id"],
                        category=category_code,
                    )
                refresh_after_notification = True
            except MockScenarioError as error:
                st.session_state.last_result = None
                st.session_state.analysis_error = {
                    "code": error.code,
                    "stage": error.stage,
                    "message": error.user_message,
                    "next_action": error.next_action,
                    "retryable": error.retryable,
                }
                add_notification(
                    st.session_state.notifications,
                    "ANALYSIS_FAILED",
                    "사례 분석을 완료하지 못했습니다.",
                    f"{error.stage}: {error.user_message}",
                    severity="error",
                    target_type="analysis",
                    category=category_code,
                )
                refresh_after_notification = True
            except ValueError as error:
                st.error(str(error))
            finally:
                st.session_state.analysis_in_progress = False
            if refresh_after_notification:
                st.rerun()
        if st.session_state.analysis_error:
            render_analysis_error(st.session_state.analysis_error)
        with summary_column:
            render_analysis_summary(st.session_state.last_result)
        if st.session_state.last_result:
            if settings.frontend_data_mode.lower() == "mock":
                render_analysis_progress(completed=True)
            render_analysis_result(st.session_state.last_result)
            render_follow_up_chat(st.session_state.last_result, service)
    elif feature == "admin_faq":
        render_admin_faq()
    else:
        if feature == "faq" and st.session_state.current_user["role"] == "ADMIN":
            if st.button("FAQ 관리", key="open-admin-faq"):
                st.session_state.selected_feature = "admin_faq"
                st.rerun()
        render_helper_feature(category_code, feature, service)

    st.markdown('<div class="footer-note">본 서비스는 법률 자문이 아니며 실제 사건의 승패를 예측하지 않습니다. 제공 정보는 참고용입니다.</div>', unsafe_allow_html=True)


if st.session_state.current_page == "home":
    render_home()
else:
    render_workspace()
