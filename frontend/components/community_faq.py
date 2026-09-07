from datetime import datetime

import streamlit as st

from frontend.data.categories import CATEGORIES
from frontend.services.mock_community_service import (
    can_comment_question,
    can_edit_question,
    can_view_question,
    create_comment,
    create_question,
    delete_comment as remove_comment,
    filter_public_questions,
    paginate_questions,
    update_comment,
    verify_question_password,
)
from frontend.services.mock_notification_service import add_notification


CATEGORY_LABELS = {"all": "전체", **{item.code: item.name for item in CATEGORIES.values()}}
STATUS_LABELS = {"all": "전체", "PENDING": "답변 대기", "ANSWERED": "답변 완료"}


def _format_time(value: str) -> str:
    return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M")


def _submit_question(category: str, title: str, content: str, password: str, password_confirm: str, is_private: bool, privacy_checked: bool) -> None:
    if len(title.strip()) < 2:
        st.error("제목을 2자 이상 입력해 주세요.")
        return
    if len(content.strip()) < 10:
        st.error("질문 내용을 10자 이상 입력해 주세요.")
        return
    if not privacy_checked:
        st.error("개인정보 주의사항을 확인해 주세요.")
        return
    if password != password_confirm:
        st.error("게시글 비밀번호 확인이 일치하지 않습니다.")
        return
    try:
        item = create_question(st.session_state.current_user, category, title, content, not is_private, password)
    except ValueError as error:
        st.error(str(error))
        return
    st.session_state.public_questions.append(item)
    add_notification(
        st.session_state.notifications,
        "QUESTION_CREATED",
        "질문이 등록되었습니다.",
        f"'{item['title']}' 질문은 답변 대기 상태입니다.",
        severity="success",
        target_type="question",
        target_id=item["id"],
        category=item["category"],
    )
    st.session_state.question_page = 1
    st.success("질문을 등록했습니다. 현재는 Mock 데이터로 Session에만 저장됩니다.")
    st.rerun()


def _delete_question(question_id: str) -> None:
    st.session_state.public_questions = [item for item in st.session_state.public_questions if item["id"] != question_id]
    st.session_state.question_edit_id = None
    st.session_state.unlocked_question_ids.discard(question_id)


def _save_edit(question_id: str, title: str, content: str, is_private: bool) -> None:
    for item in st.session_state.public_questions:
        if item["id"] == question_id and can_edit_question(item, st.session_state.current_user):
            item["title"] = title.strip()
            item["content"] = content.strip()
            item["visibility"] = "PRIVATE" if is_private else "PUBLIC"
            item["content_visibility"] = "OWNER_ONLY" if is_private else "PUBLIC"
            item["updated_at"] = datetime.now().replace(microsecond=0).isoformat()
            st.session_state.question_edit_id = None
            return


def _ask_again(item: dict) -> None:
    copied = create_question(st.session_state.current_user, item["category"], f"{item['title']} (다시 질문)", item["content"], item["visibility"] == "PUBLIC", "temporary-demo")
    copied["password_hash"] = item["password_hash"]
    st.session_state.public_questions.append(copied)
    st.session_state.unlocked_question_ids.add(copied["id"])
    st.session_state.question_page = 1


def _unlock_question(question_id: str, password: str) -> None:
    question = next((item for item in st.session_state.public_questions if item["id"] == question_id), None)
    if not question or not can_edit_question(question, st.session_state.current_user):
        st.error("본인 질문만 확인할 수 있습니다.")
        return
    if not verify_question_password(question, password):
        st.error("게시글 비밀번호가 올바르지 않습니다.")
        return
    st.session_state.unlocked_question_ids.add(question_id)


def _set_question_page(page: int) -> None:
    """Streamlit 재실행 전 목표 페이지를 명시적으로 저장한다."""
    total_pages = st.session_state.get("question_total_pages", 1)
    st.session_state.question_page = max(1, min(page, total_pages))


def _submit_comment(question: dict, content: str, password: str) -> None:
    user = st.session_state.current_user
    is_unlocked = question["id"] in st.session_state.unlocked_question_ids
    if not can_comment_question(question, user, is_unlocked):
        st.error("이 글에는 작성자와 관리자만 댓글을 작성할 수 있습니다.")
        return
    try:
        comment = create_comment(question, user, content, password)
    except ValueError as error:
        st.error(str(error))
        return
    question.setdefault("comments", []).append(comment)
    add_notification(
        st.session_state.notifications,
        "COMMENT_CREATED",
        "댓글이 등록되었습니다.",
        "비밀글의 상세 내용은 알림에 표시하지 않습니다." if question["visibility"] == "PRIVATE" else f"'{question['title']}' 글에 댓글을 등록했습니다.",
        severity="success",
        target_type="question",
        target_id=question["id"],
        category=question["category"],
    )
    st.success("댓글을 등록했습니다.")
    st.rerun()


def _save_comment(comment: dict, content: str, password: str) -> None:
    try:
        update_comment(comment, st.session_state.current_user, content, password)
    except (ValueError, PermissionError) as error:
        st.error(str(error))
        return
    st.success("댓글을 수정했습니다.")
    st.rerun()


def _delete_comment(question: dict, comment: dict, password: str) -> None:
    try:
        remove_comment(question, comment, st.session_state.current_user, password)
    except PermissionError as error:
        st.error(str(error))
        return
    st.success("댓글을 삭제했습니다.")
    st.rerun()


def _render_comments(question: dict, is_unlocked: bool) -> None:
    user = st.session_state.current_user
    st.markdown("#### 💬 댓글")
    st.caption("사용자 댓글은 공식 법률 답변이나 법률 자문이 아닙니다.")
    comments = sorted(question.get("comments", []), key=lambda item: item["created_at"])
    if not comments:
        st.info("등록된 댓글이 없습니다.")
    for comment in comments:
        role_badge = "🛡 관리자" if comment["owner_role"] == "ADMIN" else comment["display_name"]
        st.markdown(f"**{role_badge}** · {_format_time(comment['created_at'])}")
        st.write(comment["content"])
        if comment["updated_at"] != comment["created_at"]:
            st.caption("수정됨")
        is_comment_owner = comment["owner_id"] == user["id"]
        if is_comment_owner or user["role"] == "ADMIN":
            with st.expander("댓글 수정·삭제", expanded=False):
                if is_comment_owner:
                    with st.form(f"comment-edit-{comment['id']}"):
                        edited = st.text_area("댓글 수정", value=comment["content"], max_chars=1000, key=f"comment-edit-content-{comment['id']}")
                        edit_password = ""
                        if user["role"] == "GUEST":
                            edit_password = st.text_input("댓글 비밀번호", type="password", key=f"comment-edit-password-{comment['id']}")
                        if st.form_submit_button("댓글 수정 저장"):
                            _save_comment(comment, edited, edit_password)
                with st.form(f"comment-delete-{comment['id']}"):
                    delete_password = ""
                    if user["role"] == "GUEST":
                        delete_password = st.text_input("삭제 확인 비밀번호", type="password", key=f"comment-delete-password-{comment['id']}")
                    if st.form_submit_button("댓글 삭제"):
                        _delete_comment(question, comment, delete_password)

    if can_comment_question(question, user, is_unlocked):
        with st.form(f"comment-create-{question['id']}", clear_on_submit=True):
            content = st.text_area("댓글 작성", max_chars=1000, key=f"comment-content-{question['id']}")
            password = ""
            if user["role"] == "GUEST":
                password = st.text_input("댓글 비밀번호", type="password", max_chars=20, key=f"comment-password-{question['id']}", help="비회원 댓글 수정·삭제에 사용할 4~20자 비밀번호입니다.")
            if st.form_submit_button("댓글 등록", type="primary", use_container_width=True):
                _submit_comment(question, content, password)


def render_community_faq(category_code: str) -> None:
    st.markdown("### 📌 자주 하는 질문")
    st.caption("모든 사용자가 확인할 수 있는 안내입니다.")
    articles = sorted(
        [item for item in st.session_state.faq_articles if item["is_active"] and item["category"] in (category_code, "all")],
        key=lambda item: (not item["is_pinned"], item["display_order"]),
    )
    for item in articles:
        label = f"📌 {item['question']}" if item["is_pinned"] else item["question"]
        with st.expander(label):
            st.write(item["answer"])

    st.divider()
    st.markdown("### 💬 사용자 질문")
    st.caption("공개글은 누구나 내용과 댓글을 볼 수 있고, 비밀글은 작성자와 관리자만 내용과 댓글을 확인할 수 있습니다.")
    user = st.session_state.current_user
    policy = "작성일로부터 7일 보관 예정" if user["role"] == "GUEST" else "회원 계정에 영구보관 예정"
    st.info(f"{user['display_name']} · {policy} · 현재는 실제 저장이 아닌 Mock Session입니다.")

    with st.expander("✍️ 질문 작성하기"):
        with st.form("community-question-create", clear_on_submit=True):
            question_category = st.selectbox("분야", options=[item.code for item in CATEGORIES.values()], format_func=lambda code: CATEGORY_LABELS[code], key="new-question-category")
            title = st.text_input("제목", max_chars=100, key="new-question-title")
            content = st.text_area("질문 내용", max_chars=2000, height=130, key="new-question-content")
            password = st.text_input("게시글 비밀번호", type="password", max_chars=20, key="new-question-password", help="내용 확인·수정·삭제에 사용할 4~20자 비밀번호입니다.")
            password_confirm = st.text_input("게시글 비밀번호 확인", type="password", max_chars=20, key="new-question-password-confirm")
            is_private = st.checkbox("🔒 비밀글로 작성", value=True, key="new-question-private", help="체크를 해제하면 제목·본문·댓글이 모든 사용자에게 공개됩니다.")
            if not is_private:
                st.warning("공개글은 제목, 질문 내용과 댓글을 누구나 볼 수 있습니다. 개인정보를 입력하지 마세요.")
            privacy_checked = st.checkbox("이름, 연락처, 주소, 계좌번호 등 개인정보를 작성하지 않았습니다.", key="new-question-privacy")
            submitted = st.form_submit_button("질문 등록", type="primary", use_container_width=True)
        if submitted:
            _submit_question(question_category, title, content, password, password_confirm, is_private, privacy_checked)

    filter_columns = st.columns([1, 1, 2])
    category_filter = filter_columns[0].selectbox("분야 필터", list(CATEGORY_LABELS), format_func=CATEGORY_LABELS.get, key="public-question-category")
    status_filter = filter_columns[1].selectbox("상태 필터", list(STATUS_LABELS), format_func=STATUS_LABELS.get, key="public-question-status")
    query = filter_columns[2].text_input("질문 검색", key="public-question-query")
    signature = (category_filter, status_filter, query)
    if st.session_state.get("question_filter_signature") != signature:
        st.session_state.question_filter_signature = signature
        st.session_state.question_page = 1

    filtered = filter_public_questions(st.session_state.public_questions, category_filter, status_filter, query)
    page = paginate_questions(filtered, st.session_state.question_page, st.session_state.question_page_size)
    st.session_state.question_page = page["page"]
    st.session_state.question_total_pages = page["total_pages"]
    st.caption(f"전체 {page['total_items']}건 · {page['page']}/{page['total_pages']} 페이지")

    if not page["items"]:
        st.info("조건에 맞는 사용자 질문이 없습니다.")
    for item in page["items"]:
        with st.container(border=True):
            badge = STATUS_LABELS.get(item["status"], item["status"])
            visibility_badge = "🌐 공개글" if item["visibility"] == "PUBLIC" else "🔒 비밀글"
            st.caption(f"{CATEGORY_LABELS[item['category']]} · {visibility_badge} · {badge} · {item['display_name']} · {_format_time(item['created_at'])}")
            st.markdown(f"**{'🔒 ' if item['visibility'] == 'PRIVATE' else ''}{item['title']}**")
            if item.get("expires_at"):
                st.caption(f"비회원 Mock 만료 예정: {_format_time(item['expires_at'])}")
            is_owner = can_edit_question(item, user)
            is_unlocked = item["id"] in st.session_state.unlocked_question_ids
            content_visible = can_view_question(item, user, is_unlocked)
            needs_owner_unlock = is_owner and not is_unlocked
            if item["visibility"] == "PRIVATE" and needs_owner_unlock:
                st.info("🔒 본인 비밀글입니다. 게시글 비밀번호를 입력하면 내용과 댓글을 확인할 수 있습니다.")
                with st.form(f"unlock-form-{item['id']}"):
                    unlock_password = st.text_input("게시글 비밀번호", type="password", key=f"unlock-password-{item['id']}")
                    unlock_submitted = st.form_submit_button("내 글 확인", use_container_width=True)
                if unlock_submitted:
                    _unlock_question(item["id"], unlock_password)
                    if item["id"] in st.session_state.unlocked_question_ids:
                        st.rerun()
            elif item["visibility"] == "PRIVATE" and not content_visible:
                st.info("🔒 비밀글입니다. 작성자와 관리자만 내용과 댓글을 확인할 수 있습니다.")
            elif content_visible:
                st.markdown("**질문 내용**")
                st.write(item["content"])
                if item.get("answer"):
                    with st.expander("답변 보기"):
                        st.write(item["answer"])
                        st.caption("화면 확인용 DEMO 답변입니다.")
                _render_comments(item, is_unlocked)

            if item["visibility"] == "PUBLIC" and needs_owner_unlock:
                with st.expander("🔑 내 글 수정·삭제 권한 확인"):
                    with st.form(f"unlock-form-{item['id']}"):
                        unlock_password = st.text_input("게시글 비밀번호", type="password", key=f"unlock-password-{item['id']}")
                        unlock_submitted = st.form_submit_button("내 글 확인", use_container_width=True)
                    if unlock_submitted:
                        _unlock_question(item["id"], unlock_password)
                        if item["id"] in st.session_state.unlocked_question_ids:
                            st.rerun()

            if is_owner and is_unlocked:
                action_columns = st.columns(3)
                if item["status"] == "ANSWERED":
                    action_columns[0].button("수정해서 다시 질문", key=f"ask-again-{item['id']}", on_click=_ask_again, args=(item,), use_container_width=True)
                else:
                    action_columns[0].button("수정", key=f"edit-{item['id']}", on_click=lambda qid=item["id"]: st.session_state.update(question_edit_id=qid), use_container_width=True)
                action_columns[1].button("삭제", key=f"delete-{item['id']}", on_click=_delete_question, args=(item["id"],), use_container_width=True)
            if st.session_state.question_edit_id == item["id"]:
                with st.form(f"edit-form-{item['id']}"):
                    edited_title = st.text_input("제목 수정", value=item["title"])
                    edited_content = st.text_area("내용 수정", value=item["content"])
                    edited_private = st.checkbox("🔒 비밀글", value=item["visibility"] == "PRIVATE", key=f"edit-private-{item['id']}")
                    if st.form_submit_button("수정 저장", type="primary"):
                        _save_edit(item["id"], edited_title, edited_content, edited_private)
                        st.rerun()

    page_numbers = list(range(1, page["total_pages"] + 1))
    controls = st.columns([1, *([0.55] * len(page_numbers)), 1])
    controls[0].button(
        "← 이전",
        key="question-prev",
        disabled=not page["has_previous"],
        on_click=_set_question_page,
        args=(page["page"] - 1,),
        use_container_width=True,
    )
    for index, page_number in enumerate(page_numbers, start=1):
        controls[index].button(
            str(page_number),
            key=f"question-page-{page_number}",
            disabled=page_number == page["page"],
            on_click=_set_question_page,
            args=(page_number,),
            use_container_width=True,
        )
    controls[-1].button(
        "다음 →",
        key="question-next",
        disabled=not page["has_next"],
        on_click=_set_question_page,
        args=(page["page"] + 1,),
        use_container_width=True,
    )
