from datetime import datetime
from html import escape

import streamlit as st

from frontend.clients import backend_client
from frontend.data.categories import CATEGORIES


CATEGORY_LABELS = {item.code: item.name for item in CATEGORIES.values()}
STATUS_LABELS = {"PENDING": "답변 대기", "ANSWERED": "답변 완료"}


def _context() -> tuple[str | None, str]:
    return st.session_state.auth_token, f"guest-{st.session_state.session_id}"


def _call(action, *args, **kwargs):
    try:
        return action(*args, **kwargs)
    except backend_client.BackendClientError as error:
        st.error(error.user_message)
        return None


def _format_time(value: str | None) -> str:
    if not value:
        return "시간 정보 없음"
    return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M")


def _role_label(item: dict) -> str:
    role = item.get("owner_role") or item.get("author_role")
    if role == "ADMIN":
        return "관리자"
    if role == "USER":
        return "회원"
    return "비회원"


def _render_question_badges(item: dict) -> None:
    status_class = "pending" if item["status"] == "PENDING" else "answered"
    visibility_class = "public" if item["visibility"] == "PUBLIC" else "private"
    visibility = "🌐 공개글" if item["visibility"] == "PUBLIC" else "🔒 비밀글"
    st.markdown(
        '<div class="question-meta">'
        f'<span class="question-badge {status_class}">{STATUS_LABELS[item["status"]]}</span>'
        f'<span class="question-badge {visibility_class}">{visibility}</span>'
        f'<span class="question-badge role">👤 {_role_label(item)}</span>'
        f'<span class="question-category">{escape(CATEGORY_LABELS[item["category"]])}</span>'
        "</div>",
        unsafe_allow_html=True,
    )


def _sort_question_items(items: list[dict]) -> list[dict]:
    """현재 페이지 안에서 답변 대기 우선, 각 상태 안에서는 최신순으로 정렬한다."""
    pending = sorted((item for item in items if item["status"] == "PENDING"), key=lambda item: item.get("created_at", ""), reverse=True)
    answered = sorted((item for item in items if item["status"] != "PENDING"), key=lambda item: item.get("created_at", ""), reverse=True)
    return [*pending, *answered]


def _render_comments(question: dict) -> None:
    token, guest_id = _context()
    payload = _call(backend_client.list_comments, token, guest_id, question["id"])
    if payload is None:
        return
    st.markdown("#### 💬 댓글")
    st.caption("사용자 댓글은 공식 법률 답변이나 법률 자문이 아닙니다.")
    comments = payload.get("items", [])
    if not comments:
        st.info("등록된 댓글이 없습니다.")
    for comment in comments:
        st.markdown(f"**{'🛡 관리자' if comment.get('owner_role') == 'ADMIN' else comment.get('display_name', '사용자')}** · {_format_time(comment.get('created_at'))}")
        st.write(comment.get("content", ""))
        if comment.get("is_owner") or st.session_state.current_user["role"] == "ADMIN":
            with st.expander("댓글 수정·삭제"):
                if comment.get("is_owner"):
                    with st.form(f"api-comment-edit-{comment['id']}"):
                        content = st.text_area("댓글 수정", value=comment.get("content", ""), key=f"api-comment-edit-content-{comment['id']}")
                        password = None
                        if st.session_state.current_user["role"] == "GUEST":
                            password = st.text_input("댓글 비밀번호", type="password", key=f"api-comment-edit-password-{comment['id']}")
                        if st.form_submit_button("댓글 수정 저장"):
                            if _call(backend_client.update_comment_api, token, guest_id, question["id"], comment["id"], content, password) is not None:
                                st.rerun()
                with st.form(f"api-comment-delete-{comment['id']}"):
                    password = None
                    if st.session_state.current_user["role"] == "GUEST":
                        password = st.text_input("삭제 확인 비밀번호", type="password", key=f"api-comment-delete-password-{comment['id']}")
                    if st.form_submit_button("댓글 삭제"):
                        if _call(backend_client.delete_comment_api, token, guest_id, question["id"], comment["id"], password) is not None:
                            st.rerun()
    with st.form(f"api-comment-create-{question['id']}", clear_on_submit=True):
        content = st.text_area("댓글 작성", max_chars=1000, key=f"api-comment-content-{question['id']}")
        password = None
        if st.session_state.current_user["role"] == "GUEST":
            password = st.text_input("댓글 비밀번호", type="password", key=f"api-comment-password-{question['id']}")
        if st.form_submit_button("댓글 등록", type="primary", use_container_width=True):
            if _call(backend_client.create_comment_api, token, guest_id, question["id"], content, password) is not None:
                st.rerun()


def _render_question_detail(item: dict) -> None:
    token, guest_id = _context()
    is_unlocked = item["id"] in st.session_state.unlocked_question_ids
    if item["visibility"] == "PRIVATE" and item.get("is_owner") and not is_unlocked and st.session_state.current_user["role"] != "ADMIN":
        st.info("본인 비밀글입니다. 게시글 비밀번호를 입력해 주세요.")
        with st.form(f"api-unlock-{item['id']}"):
            password = st.text_input("게시글 비밀번호", type="password", key=f"api-unlock-password-{item['id']}")
            if st.form_submit_button("내 글 확인"):
                if _call(backend_client.unlock_question, token, guest_id, item["id"], password) is not None:
                    st.session_state.unlocked_question_ids.add(item["id"])
                    st.rerun()
        return
    if item["visibility"] == "PRIVATE" and not item.get("is_owner") and st.session_state.current_user["role"] != "ADMIN":
        st.info("비밀글입니다. 작성자와 관리자만 확인할 수 있습니다.")
        return
    detail = _call(backend_client.get_question, token, guest_id, item["id"])
    if detail is None:
        return
    st.markdown("**질문 내용**")
    st.write(detail.get("content", ""))
    if detail.get("answer"):
        with st.expander("답변 보기"):
            st.write(detail["answer"])
    _render_comments(detail)
    is_admin = st.session_state.current_user["role"] == "ADMIN"
    can_edit = item.get("is_owner") and item["status"] == "PENDING"
    can_delete = item.get("is_owner") or is_admin
    if can_edit or can_delete:
        with st.expander("질문 관리" if is_admin else "내 질문 수정·삭제"):
            if can_edit:
                with st.form(f"api-question-edit-{item['id']}"):
                    title = st.text_input("제목 수정", value=detail.get("title", item["title"]))
                    content = st.text_area("내용 수정", value=detail.get("content", ""))
                    private = st.checkbox("비밀글", value=item["visibility"] == "PRIVATE")
                    password = st.text_input("게시글 비밀번호", type="password", key=f"api-edit-password-{item['id']}")
                    if st.form_submit_button("수정 저장"):
                        body = {"title": title, "content": content, "post_password": password, "visibility": "PRIVATE" if private else "PUBLIC"}
                        if _call(backend_client.update_question_api, token, guest_id, item["id"], body) is not None:
                            st.toast("질문을 수정했습니다.", icon="✅")
                            st.rerun()
            with st.form(f"api-question-delete-{item['id']}"):
                if is_admin:
                    st.warning("관리자 권한으로 게시글을 삭제합니다. Backend의 관리자 삭제 권한이 필요합니다.")
                    reason = st.text_input("삭제 사유", key=f"api-admin-delete-reason-{item['id']}")
                    password = ""
                else:
                    reason = None
                    password = st.text_input("삭제 확인 비밀번호", type="password", key=f"api-delete-password-{item['id']}")
                confirm = st.checkbox("삭제 후 복구할 수 없음을 확인했습니다.", key=f"api-delete-confirm-{item['id']}")
                if st.form_submit_button("질문 삭제"):
                    if not confirm:
                        st.warning("삭제 확인을 체크해 주세요.")
                    elif is_admin and not reason.strip():
                        st.warning("관리자 삭제 사유를 입력해 주세요.")
                    elif _call(backend_client.delete_question_api, token, guest_id, item["id"], password, reason=reason) is not None:
                        st.toast("질문을 삭제했습니다.", icon="🗑️")
                        st.rerun()


def render_api_community_faq(category_code: str) -> None:
    st.markdown("### 📌 자주 하는 질문")
    faqs = _call(backend_client.list_faqs, category_code)
    for item in (faqs or {}).get("items", []):
        with st.expander(f"{'📌 ' if item.get('is_pinned') else ''}{item['question']}"):
            st.write(item["answer"])

    st.divider()
    st.markdown("### 💬 사용자 질문")
    st.caption("API 모드 · 공개글은 모두 열람·댓글 작성, 비밀글은 작성자와 관리자만 접근합니다.")
    token, guest_id = _context()
    if st.session_state.get("question_create_flash"):
        flash = st.session_state.pop("question_create_flash")
        st.success(f"질문이 등록되었습니다. 게시글 번호: {flash['id']}")
        st.toast("질문 등록이 완료되었습니다.", icon="✅")
    if st.session_state.pop("reset_question_form", False):
        st.session_state["api-new-question-category"] = category_code
        st.session_state["api-question-title"] = ""
        st.session_state["api-question-content"] = ""
        st.session_state["api-question-password"] = ""
        st.session_state["api-question-private"] = True
        st.session_state["api-question-privacy"] = False
    with st.expander("질문 작성"):
        with st.form("api-question-create", clear_on_submit=False):
            category = st.selectbox("분야", list(CATEGORY_LABELS), index=list(CATEGORY_LABELS).index(category_code), key="api-new-question-category")
            title = st.text_input("제목", max_chars=100, key="api-question-title")
            content = st.text_area("질문 내용", max_chars=2000, key="api-question-content")
            password = st.text_input("게시글 비밀번호", type="password", max_chars=20, key="api-question-password")
            private = st.checkbox("🔒 비밀글로 작성", value=True, key="api-question-private")
            privacy = st.checkbox("개인정보를 작성하지 않았습니다.", key="api-question-privacy")
            if st.form_submit_button("질문 등록", type="primary", use_container_width=True):
                if not privacy:
                    st.warning("개인정보 미작성 확인이 필요합니다. 작성한 제목과 내용은 그대로 유지됩니다.")
                else:
                    body = {"category": category, "title": title, "content": content, "post_password": password, "visibility": "PRIVATE" if private else "PUBLIC", "privacy_confirmed": privacy}
                    created = _call(backend_client.create_question_api, token, guest_id, body)
                    if created is not None:
                        st.session_state.question_create_flash = {"id": created.get("id", "확인 중")}
                        st.session_state.reset_question_form = True
                        st.session_state.question_page = 1
                        st.rerun()

    columns = st.columns([1, 1, 2])
    category_filter = columns[0].selectbox("분야 필터", ["all", *CATEGORY_LABELS], format_func=lambda value: "전체" if value == "all" else CATEGORY_LABELS[value], key="api-question-category")
    status = columns[1].selectbox("상태", ["all", "PENDING", "ANSWERED"], format_func=lambda value: "전체" if value == "all" else STATUS_LABELS[value], key="api-question-status")
    query = columns[2].text_input("제목·공개 본문 검색", key="api-question-query")
    params = {"page": st.session_state.question_page, "page_size": st.session_state.question_page_size, "query": query}
    if category_filter != "all":
        params["category"] = category_filter
    if status != "all":
        params["status"] = status
    payload = _call(backend_client.list_questions, token, guest_id, **params)
    if payload is None:
        return
    page = payload["pagination"]
    st.caption(f"전체 {page['total_items']}건 · {page['page']}/{page['total_pages']} 페이지")
    items = _sort_question_items(payload["items"])
    for item in items:
        with st.container(border=True):
            _render_question_badges(item)
            st.markdown(f'<div class="question-title">{escape(item["title"])}</div>', unsafe_allow_html=True)
            st.caption(f"{item['display_name']} · {_format_time(item.get('created_at'))}")
            _render_question_detail(item)
    previous, _, next_button = st.columns([1, 3, 1])
    if previous.button("이전", disabled=not page["has_previous"], use_container_width=True):
        st.session_state.question_page -= 1
        st.rerun()
    if next_button.button("다음", disabled=not page["has_next"], use_container_width=True):
        st.session_state.question_page += 1
        st.rerun()
