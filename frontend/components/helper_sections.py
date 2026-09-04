import streamlit as st

from frontend.core.session import restore_history_item
from frontend.data.mock_catalog import MOCK_CATALOG
from frontend.services.base import LegalService


def _clear_checklist(keys: list[str]) -> None:
    for key in keys:
        st.session_state[key] = False


def render_helper_feature(category: str, feature: str, service: LegalService) -> None:
    data = MOCK_CATALOG[category]
    if feature == "terms":
        _render_terms(category, service)
    elif feature == "documents":
        _render_checklist(category, "필요 서류", data["documents"], "doc")
    elif feature == "actions":
        _render_checklist(category, "다음 행동", data["actions"], "action", numbered=True)
    elif feature == "faq":
        _render_faq(category, data["faqs"])
    elif feature == "history":
        _render_history()


def _render_terms(category: str, service: LegalService) -> None:
    st.markdown("### ▣ 쉬운 법률 용어")
    query = st.text_input("용어 검색", key=f"term-query-{category}", placeholder="용어나 설명을 검색하세요")
    results = service.search_terms(category, query)
    if not results:
        st.info("검색 결과가 없습니다.")
    for term, description in results:
        with st.container(border=True):
            st.markdown(f"**{term}**")
            st.write(description)


def _render_checklist(category: str, title: str, items: list[str], kind: str, numbered: bool = False) -> None:
    icon = "□" if kind == "doc" else "◷"
    st.markdown(f"### {icon} {title}")
    keys = [f"{kind}-{category}-{index}" for index in range(len(items))]
    completed = sum(bool(st.session_state.get(key, False)) for key in keys)
    st.progress(completed / len(items), text=f"진행률 {completed}/{len(items)}")
    for index, (key, item) in enumerate(zip(keys, items, strict=True), 1):
        label = f"{index}. {item}" if numbered else item
        st.checkbox(label, key=key)
    st.button("전체 초기화", key=f"reset-{kind}-{category}", on_click=_clear_checklist, args=(keys,), use_container_width=True)
    st.info("체크 상태는 현재 브라우저 세션에서만 유지됩니다.")


def _render_faq(category: str, faqs: list[tuple[str, str]]) -> None:
    st.markdown("### ? FAQ")
    query = st.text_input("FAQ 검색", key=f"faq-query-{category}", placeholder="궁금한 내용을 검색하세요")
    normalized = query.strip().lower()
    filtered = [item for item in faqs if not normalized or normalized in f"{item[0]} {item[1]}".lower()]
    if not filtered:
        st.info("검색 결과가 없습니다.")
    for question, answer in filtered:
        with st.expander(question):
            st.write(answer)


def _render_history() -> None:
    st.markdown("### ↶ 질의 이력")
    history = st.session_state.session_history
    if not history:
        st.markdown('<div class="coming-soon">아직 분석한 사례가 없습니다.</div>', unsafe_allow_html=True)
        return
    if st.button("전체 이력 삭제", type="secondary", use_container_width=True):
        st.session_state.session_history = []
        st.session_state.last_result = None
        st.rerun()
    for reverse_index, item in enumerate(reversed(history)):
        original_index = len(history) - reverse_index - 1
        with st.container(border=True):
            st.caption(f"{item['agent_id']} · 현재 세션에만 저장됨")
            st.markdown(f"**{item['question']}**")
            st.write(item["question_summary"])
            load_column, delete_column = st.columns(2)
            if load_column.button("다시 보기", key=f"history-load-{item['request_id']}", use_container_width=True):
                restore_history_item(item)
                st.rerun()
            if delete_column.button("삭제", key=f"history-delete-{item['request_id']}", use_container_width=True):
                st.session_state.session_history.pop(original_index)
                st.rerun()


def render_dashboard_helpers(category: str) -> None:
    data = MOCK_CATALOG[category]
    columns = st.columns(4, gap="small")
    with columns[0]:
        with st.container(border=True):
            st.markdown("**▣ 쉬운 법률 용어**")
            for term, description in data["terms"][:2]:
                st.markdown(f"**{term}**")
                st.caption(description)
    with columns[1]:
        with st.container(border=True):
            st.markdown("**□ 필요 서류**")
            for item in data["documents"][:4]:
                st.markdown(f"○ {item}")
    with columns[2]:
        with st.container(border=True):
            st.markdown("**◷ 다음 행동**")
            for index, item in enumerate(data["actions"][:5], 1):
                st.markdown(f"{index}. {item}")
    with columns[3]:
        with st.container(border=True):
            st.markdown("**? FAQ**")
            for question, _ in data["faqs"]:
                st.markdown(f"⌄ {question}")
