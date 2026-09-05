from uuid import uuid4

import streamlit as st

from frontend.data.categories import CATEGORIES


def _move_faq(faq_id: str, direction: int) -> None:
    ordered = sorted(st.session_state.faq_articles, key=lambda row: row["display_order"])
    index = next((idx for idx, row in enumerate(ordered) if row["id"] == faq_id), None)
    if index is None:
        return
    target = index + direction
    if 0 <= target < len(ordered):
        ordered[index]["display_order"], ordered[target]["display_order"] = ordered[target]["display_order"], ordered[index]["display_order"]


def _save_faq(faq_id: str, question: str, answer: str, category: str) -> None:
    for item in st.session_state.faq_articles:
        if item["id"] == faq_id:
            item.update(question=question.strip(), answer=answer.strip(), category=category)
            st.session_state.admin_faq_edit_id = None
            return


def render_admin_faq() -> None:
    if st.session_state.current_user["role"] != "ADMIN":
        st.error("관리자 Mock 역할에서만 확인할 수 있습니다.")
        return
    st.markdown("### 🛠 관리자 FAQ 관리 · MOCK")
    st.warning("실제 관리자 인증이나 DB 변경이 아닌 현재 Session의 화면 검증 기능입니다.")
    with st.form("admin-faq-create", clear_on_submit=True):
        category = st.selectbox("분야", [item.code for item in CATEGORIES.values()])
        question = st.text_input("질문")
        answer = st.text_area("답변")
        pinned = st.checkbox("상단 고정")
        if st.form_submit_button("FAQ 추가", type="primary") and question.strip() and answer.strip():
            st.session_state.faq_articles.append({"id": f"faq-{uuid4()}", "category": category, "question": question.strip(), "answer": answer.strip(), "is_pinned": pinned, "is_active": True, "display_order": len(st.session_state.faq_articles) + 1})

    for item in sorted(st.session_state.faq_articles, key=lambda row: row["display_order"]):
        with st.container(border=True):
            st.markdown(f"**{'📌 ' if item['is_pinned'] else ''}{item['question']}**")
            st.write(item["answer"])
            st.caption(f"{item['category']} · {'공개' if item['is_active'] else '비공개'} · 순서 {item['display_order']}")
            columns = st.columns(5)
            if columns[0].button("공개 전환", key=f"admin-active-{item['id']}", use_container_width=True):
                item["is_active"] = not item["is_active"]
                st.rerun()
            if columns[1].button("고정 전환", key=f"admin-pin-{item['id']}", use_container_width=True):
                item["is_pinned"] = not item["is_pinned"]
                st.rerun()
            if columns[2].button("수정", key=f"admin-edit-{item['id']}", use_container_width=True):
                st.session_state.admin_faq_edit_id = item["id"]
                st.rerun()
            columns[3].button("↑", key=f"admin-up-{item['id']}", on_click=_move_faq, args=(item["id"], -1), use_container_width=True)
            columns[4].button("↓", key=f"admin-down-{item['id']}", on_click=_move_faq, args=(item["id"], 1), use_container_width=True)
            if st.session_state.admin_faq_edit_id == item["id"]:
                with st.form(f"admin-edit-form-{item['id']}"):
                    edit_category = st.selectbox("분야 수정", [category.code for category in CATEGORIES.values()], index=list(CATEGORIES).index(item["category"]))
                    edit_question = st.text_input("질문 수정", value=item["question"])
                    edit_answer = st.text_area("답변 수정", value=item["answer"])
                    if st.form_submit_button("수정 저장", type="primary"):
                        _save_faq(item["id"], edit_question, edit_answer, edit_category)
                        st.rerun()
            if st.button("FAQ 삭제", key=f"admin-delete-{item['id']}", use_container_width=True):
                st.session_state.faq_articles = [row for row in st.session_state.faq_articles if row["id"] != item["id"]]
                st.rerun()
