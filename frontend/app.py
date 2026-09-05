import streamlit as st

from frontend.components.analysis_summary import render_analysis_summary
from frontend.components.answer_view import render_analysis_result, render_case_results, render_law_results
from frontend.components.app_header import load_theme, render_header
from frontend.components.category_cards import render_category_cards
from frontend.components.helper_sections import render_dashboard_helpers, render_helper_feature
from frontend.components.question_form import render_question_form
from frontend.components.qa_panel import render_qa_panel
from frontend.components.presentation_panel import render_presentation_panel
from frontend.components.admin_faq import render_admin_faq
from frontend.components.search_forms import render_search_form
from frontend.components.sidebar import render_sidebar
from frontend.core.session import initialize_session
from frontend.data.categories import get_category
from frontend.core.config import get_frontend_settings
from frontend.services.factory import get_legal_service


st.set_page_config(page_title="LawPath", page_icon="⚖️", layout="wide", initial_sidebar_state="expanded")
initialize_session()
load_theme()


def render_home() -> None:
    render_header()
    st.markdown('<div class="page-kicker">LIFE LEGAL GUIDE</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-title">어떤 법률 문제를 확인하고 싶으신가요?</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-description">생활 속 법률 분야를 선택하면 사례 분석, 법 검색, 실제 사례 검색을 시작할 수 있습니다.</div>', unsafe_allow_html=True)
    render_category_cards()
    st.info("이 서비스는 법률 자문이나 판결 예측을 제공하지 않습니다. 현재 화면은 DEMO 데이터로 동작합니다.")


def render_workspace() -> None:
    category_code = st.session_state.selected_category
    if not category_code:
        st.session_state.current_page = "home"
        st.rerun()
    category = get_category(category_code)
    service = get_legal_service()
    render_sidebar(category_code)
    settings = get_frontend_settings()
    if settings.frontend_qa_mode:
        render_qa_panel(service)
    if settings.frontend_presentation_mode:
        render_presentation_panel(service)
    render_header(show_home=True)
    labels = {"analysis": "내 사례 분석", "laws": "법 검색", "cases": "실제 사례", "terms": "쉬운 법률 용어", "documents": "필요 서류", "actions": "다음 행동", "faq": "FAQ", "history": "질의 이력", "admin_faq": "FAQ 관리"}
    st.caption(f"{category.name}  ›  {labels[st.session_state.selected_feature]}")

    feature = st.session_state.selected_feature
    if feature == "analysis":
        input_column, summary_column = st.columns([1, 1.35], gap="large")
        with input_column:
            submission = render_question_form(category_code)
        if submission:
            try:
                with st.spinner("사례를 정리하고 화면용 자료를 찾고 있습니다..."):
                    result = service.analyze_case(category_code, submission.message)
                st.session_state.last_result = result
                st.session_state.session_history.append(result)
            except ValueError as error:
                st.error(str(error))
        with summary_column:
            render_analysis_summary(st.session_state.last_result)
        if st.session_state.last_result:
            render_analysis_result(st.session_state.last_result)
            render_dashboard_helpers(category_code)
    elif feature == "laws":
        query = render_search_form("laws")
        if query:
            st.session_state.law_results = service.search_laws(category_code, query)
        render_law_results(st.session_state.law_results)
    elif feature == "cases":
        query = render_search_form("cases")
        if query:
            st.session_state.case_results = service.search_cases(category_code, query)
        render_case_results(st.session_state.case_results)
    elif feature == "admin_faq":
        render_admin_faq()
    else:
        render_helper_feature(category_code, feature, service)

    st.markdown('<div class="footer-note">본 서비스는 법률 자문이 아니며 실제 사건의 승패를 예측하지 않습니다. 제공 정보는 참고용입니다.</div>', unsafe_allow_html=True)


if st.session_state.current_page == "home":
    render_home()
else:
    render_workspace()
