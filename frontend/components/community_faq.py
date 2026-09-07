from datetime import datetime

import streamlit as st

from frontend.data.categories import CATEGORIES
from frontend.services.mock_community_service import can_edit_question, create_question, filter_public_questions, paginate_questions


CATEGORY_LABELS = {"all": "전체", **{item.code: item.name for item in CATEGORIES.values()}}
STATUS_LABELS = {"all": "전체", "PENDING": "답변 대기", "ANSWERED": "답변 완료"}


def _format_time(value: str) -> str:
    return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M")


def _submit_question(category: str, title: str, content: str, is_public: bool, privacy_checked: bool) -> None:
    if len(title.strip()) < 2:
        st.error("제목을 2자 이상 입력해 주세요.")
        return
    if len(content.strip()) < 10:
        st.error("질문 내용을 10자 이상 입력해 주세요.")
        return
    if not privacy_checked:
        st.error("개인정보 주의사항을 확인해 주세요.")
        return
    item = create_question(st.session_state.current_user, category, title, content, is_public)
    st.session_state.public_questions.append(item)
    st.session_state.question_page = 1
    st.success("질문을 등록했습니다. 현재는 Mock 데이터로 Session에만 저장됩니다.")


def _delete_question(question_id: str) -> None:
    st.session_state.public_questions = [item for item in st.session_state.public_questions if item["id"] != question_id]
    st.session_state.question_edit_id = None


def _save_edit(question_id: str, title: str, content: str) -> None:
    for item in st.session_state.public_questions:
        if item["id"] == question_id and can_edit_question(item, st.session_state.current_user):
            item["title"] = title.strip()
            item["content"] = content.strip()
            item["updated_at"] = datetime.now().replace(microsecond=0).isoformat()
            st.session_state.question_edit_id = None
            return


def _ask_again(item: dict) -> None:
    copied = create_question(st.session_state.current_user, item["category"], f"{item['title']} (다시 질문)", item["content"], item["visibility"] == "PUBLIC")
    st.session_state.public_questions.append(copied)
    st.session_state.question_page = 1


def _set_question_page(page: int) -> None:
    """Streamlit 재실행 전 목표 페이지를 명시적으로 저장한다."""
    total_pages = st.session_state.get("question_total_pages", 1)
    st.session_state.question_page = max(1, min(page, total_pages))


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
    st.caption("공개에 동의한 질문이 최신순으로 표시됩니다. 작성자만 자신의 질문을 수정하거나 삭제할 수 있습니다.")
    user = st.session_state.current_user
    policy = "작성일로부터 7일 보관 예정" if user["role"] == "GUEST" else "회원 계정에 영구보관 예정"
    st.info(f"{user['display_name']} · {policy} · 현재는 실제 저장이 아닌 Mock Session입니다.")

    with st.expander("✍️ 질문 작성하기"):
        with st.form("community-question-create", clear_on_submit=True):
            question_category = st.selectbox("분야", options=[item.code for item in CATEGORIES.values()], format_func=lambda code: CATEGORY_LABELS[code], key="new-question-category")
            title = st.text_input("제목", max_chars=100, key="new-question-title")
            content = st.text_area("질문 내용", max_chars=2000, height=130, key="new-question-content")
            is_public = st.checkbox("사용자 질문 게시판에 공개", value=True, key="new-question-public")
            privacy_checked = st.checkbox("이름, 연락처, 주소, 계좌번호 등 개인정보를 작성하지 않았습니다.", key="new-question-privacy")
            submitted = st.form_submit_button("질문 등록", type="primary", use_container_width=True)
        if submitted:
            _submit_question(question_category, title, content, is_public, privacy_checked)

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
        st.info("조건에 맞는 공개 질문이 없습니다.")
    for item in page["items"]:
        with st.container(border=True):
            badge = STATUS_LABELS.get(item["status"], item["status"])
            st.caption(f"{CATEGORY_LABELS[item['category']]} · {badge} · {item['display_name']} · {_format_time(item['created_at'])}")
            st.markdown(f"**{item['title']}**")
            st.write(item["content"])
            if item.get("answer"):
                with st.expander("답변 보기"):
                    st.write(item["answer"])
                    st.caption("화면 확인용 DEMO 답변입니다.")
            if item.get("expires_at"):
                st.caption(f"비회원 Mock 만료 예정: {_format_time(item['expires_at'])}")
            if can_edit_question(item, user):
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
                    if st.form_submit_button("수정 저장", type="primary"):
                        _save_edit(item["id"], edited_title, edited_content)
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
