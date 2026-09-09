import streamlit as st

from frontend.clients import backend_client as api
from frontend.services.history_service import parse_page, load_detail

LABELS = {"analysis": "사례 분석", "legal_terms": "법률 용어 대화"}


def render_detail(item):
    if item.get("question"):
        st.text(item["question"])
    if item.get("result"):
        from frontend.services.api_legal_service import ApiLegalService
        from frontend.components.answer_view import render_analysis_result
        result = ApiLegalService.adapt_analysis(item["result"], item.get("question", ""))
        render_analysis_result(result)
    if item.get("messages"):
        for message in item["messages"]:
            with st.chat_message(message["role"]):
                st.text(message["content"])
    if not item.get("result") and not item.get("messages"):
        st.info("상세 내용이 아직 제공되지 않았습니다.")


def render_items(items, token):
    for item in items:
        key = f"history-{item['type']}-{item['id']}"
        with st.container(border=True):
            st.caption(f"{LABELS[item['type']]} · {item.get('created_at') or ''}")
            st.text(item.get("title") or item.get("question") or "저장된 대화")
            st.text(item.get("summary") or "")
            if item.get("expires_at"):
                st.caption(f"만료 시각: {item['expires_at']}")
            if st.button("상세 보기", key=key + "-open"):
                try:
                    st.session_state[key + "-detail"] = load_detail(token, item) if token else item
                except api.BackendClientError as error:
                    st.session_state.pop(key + "-detail", None)
                    st.error(error.user_message)
            detail = st.session_state.get(key + "-detail")
            if detail:
                with st.expander("저장 내용", expanded=True):
                    render_detail(detail)
            if token:
                if st.button("삭제", key=key + "-delete"):
                    st.session_state[key + "-confirm"] = True
                if st.session_state.get(key + "-confirm"):
                    st.warning("이 저장 항목을 삭제할까요?")
                    if st.button("삭제 확인", key=key + "-yes"):
                        try:
                            api.delete_saved_conversation(token, item["id"])
                            for suffix in ("-detail", "-confirm"):
                                st.session_state.pop(key + suffix, None)
                            st.rerun()
                        except api.BackendClientError as error:
                            st.error(error.user_message)
                    if st.button("취소", key=key + "-no"):
                        st.session_state.pop(key + "-confirm", None)
                        st.rerun()


def render_saved_history():
    st.markdown("### ↶ 질의 이력")
    st.caption("저장된 내용을 열람하고 삭제할 수 있습니다. 이 화면에서는 추가 질문을 보내지 않습니다.")
    selected = st.radio("이력 유형", ["all", *LABELS], format_func=lambda k: LABELS.get(k, "전체"), horizontal=True)
    token = st.session_state.auth_token
    if not token:
        st.info("비회원 이력은 임시 보관됩니다. 계속 보관하려면 회원가입 또는 로그인이 필요합니다.")
        try:
            page = parse_page(api.list_guest_temporary_history(f"guest-{st.session_state.session_id}"))
            if page["items"] and st.button("임시 이력 전체 삭제", key="history-guest-delete"):
                st.session_state["history-guest-confirm"] = True
            if st.session_state.get("history-guest-confirm"):
                st.warning("임시 이력을 모두 삭제할까요?")
                if st.button("삭제 확인", key="history-guest-yes"):
                    api.delete_guest_temporary_history(f"guest-{st.session_state.session_id}")
                    for key in list(st.session_state):
                        if key.startswith("history-"):
                            st.session_state.pop(key, None)
                    st.rerun()
                if st.button("취소", key="history-guest-no"):
                    st.session_state.pop("history-guest-confirm", None)
                    st.rerun()
            if page.get("notice"):
                st.text(page["notice"])
            if page.get("expires_at"):
                st.caption(f"임시 보관 만료 시각: {page['expires_at']}")
            elif page.get("expires_in") is not None:
                st.caption(f"서버가 반환한 남은 보관 시간: {page['expires_in']}초")
            items = [i for i in page["items"] if selected in ("all", i["type"])]
            render_items(items, None)
            if not items:
                st.info("표시할 임시 이력이 없습니다.")
        except api.BackendClientError as error:
            st.error(error.user_message)
        return
    page_number = int(st.number_input("페이지", min_value=1, step=1, key="history-page-unified"))
    try:
        raw = api.list_saved_conversations(token, page=page_number)
        page = parse_page(raw)
        if "page" not in raw:
            page["items"] = page["items"][(page_number - 1) * 20:page_number * 20]
        items = [item for item in page["items"] if selected in ("all", item["type"])]
        st.caption("이력 유형은 현재 페이지의 항목에 적용됩니다.")
        if not items:
            st.info("이 페이지에 표시할 저장 이력이 없습니다.")
        render_items(items, token)
    except api.BackendClientError as error:
        st.error(error.user_message)
