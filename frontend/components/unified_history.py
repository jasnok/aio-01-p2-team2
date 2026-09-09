import streamlit as st

from frontend.clients import backend_client
from frontend.core.config import get_frontend_settings
from frontend.core.session import restore_history_item


def render_unified_history() -> None:
    if get_frontend_settings().frontend_data_mode.lower() == "api":
        _render_api_history()
        return
    st.markdown("### ↶ 통합 질의 이력")
    user = st.session_state.current_user
    policy = "작성일로부터 7일 보관 예정" if user["role"] == "GUEST" else "회원 계정에 영구보관 예정"
    st.info(f"{policy} · 현재는 Mock Session에만 저장됩니다.")
    filter_value = st.radio("이력 유형", ["all", "analysis", "question"], format_func={"all": "전체", "analysis": "사례 분석", "question": "사용자 질문"}.get, horizontal=True)
    entries = []
    if filter_value in ("all", "analysis"):
        entries.extend({"type": "analysis", "created_at": item.get("created_at", "9999"), "item": item} for item in st.session_state.session_history)
    if filter_value in ("all", "question"):
        entries.extend({"type": "question", "created_at": item["created_at"], "item": item} for item in st.session_state.public_questions if item["owner_id"] == user["id"])
    entries.sort(key=lambda entry: entry["created_at"], reverse=True)
    if not entries:
        st.info("현재 역할로 저장된 질의 이력이 없습니다.")
        return
    for entry in entries:
        item = entry["item"]
        with st.container(border=True):
            if entry["type"] == "analysis":
                st.caption("사례 분석")
                st.markdown(f"**{item['question']}**")
                st.write(item["question_summary"])
                if st.button("분석 다시 보기", key=f"unified-analysis-{item['request_id']}"):
                    restore_history_item(item)
                    st.rerun()
            else:
                st.caption(f"사용자 질문 · {item['status']}")
                st.markdown(f"**{item['title']}**")
                if item["id"] in st.session_state.unlocked_question_ids:
                    st.write(item["content"])
                    if item.get("answer"):
                        st.write(item["answer"])
                else:
                    st.info("🔒 질문 내용은 FAQ 게시판에서 게시글 비밀번호 확인 후 볼 수 있습니다.")


def _render_api_history() -> None:
    st.markdown("### ↶ 통합 질의 이력")
    user = st.session_state.current_user
    st.info("Backend API의 이력 목록입니다. DB 영속 저장과 이전 대화 복원은 연결 확인 전입니다.")
    labels = {"all": "전체", "saved": "저장 분석", "terms": "법률 용어 대화"}
    history_type = st.radio("이력 유형", list(labels), format_func=labels.get, horizontal=True, key="api-history-type")
    token = st.session_state.auth_token
    guest_id = f"guest-{st.session_state.session_id}"
    try:
        if not token:
            payload = backend_client.list_guest_temporary_history(guest_id)
        elif history_type == "saved":
            payload = backend_client.list_saved_conversations(token)
        elif history_type == "terms":
            payload = backend_client.list_legal_term_conversations(token)
        else:
            saved = backend_client.list_saved_conversations(token)
            terms = backend_client.list_legal_term_conversations(token)
            payload = {"items": [*(saved.get("items", [])), *(terms.get("items", []))]}
    except backend_client.BackendClientError as error:
        st.error(error.user_message)
        return
    items = payload.get("items", [])
    if not items:
        st.info("저장된 질의 이력이 없습니다.")
        return
    for item in items:
        with st.container(border=True):
            item_type = item.get("type", item.get("history_type", "saved"))
            st.caption(f"{labels.get(item_type, item_type)} · {item.get('created_at', '')}")
            st.markdown(f"**{item.get('title') or item.get('question') or '질의 이력'}**")
            st.write(item.get("summary") or item.get("question_summary") or item.get("content") or "상세 내용을 확인해 주세요.")
            if st.button("이력 삭제", key=f"api-history-delete-{item['id']}"):
                try:
                    if item_type in {"terms", "legal_terms", "term_conversation"}:
                        backend_client.delete_legal_term_conversation(token, item["id"])
                    else:
                        backend_client.delete_saved_conversation(token, item["id"])
                    st.rerun()
                except backend_client.BackendClientError as error:
                    st.error(error.user_message)
