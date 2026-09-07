import streamlit as st

from frontend.clients import backend_client
from frontend.data.categories import CATEGORIES


def _body(category: str, question: str, answer: str, active: bool, pinned: bool, order: int) -> dict:
    return {"category": category, "question": question, "answer": answer, "is_active": active, "is_pinned": pinned, "display_order": order}


def render_api_admin_faq() -> None:
    if st.session_state.current_user["role"] != "ADMIN" or not st.session_state.auth_token:
        st.error("관리자 로그인이 필요합니다.")
        return
    token = st.session_state.auth_token
    st.markdown("### 🛠 관리자 FAQ 관리")
    st.caption("변경 내용은 Backend API로 전달됩니다.")
    with st.form("api-admin-faq-create", clear_on_submit=True):
        category = st.selectbox("분야", list(CATEGORIES))
        question = st.text_input("질문")
        answer = st.text_area("답변")
        pinned = st.checkbox("상단 고정")
        if st.form_submit_button("FAQ 추가", type="primary"):
            try:
                # 고정 FAQ는 일반 FAQ보다 작은 순서를 사용한다. 최종 정렬은 Backend도
                # is_pinned DESC, display_order ASC 규칙을 보장해야 한다.
                display_order = 0 if pinned else 999
                backend_client.create_admin_faq(token, _body(category, question, answer, True, pinned, display_order))
                st.toast("FAQ가 추가되었습니다.", icon="✅")
                st.rerun()
            except backend_client.BackendClientError as error:
                st.error(error.user_message)
    try:
        items = backend_client.list_admin_faqs(token).get("items", [])
    except backend_client.BackendClientError as error:
        st.error(error.user_message)
        return
    for item in items:
        with st.container(border=True):
            st.markdown(f"**{'📌 ' if item.get('is_pinned') else ''}{item['question']}**")
            st.write(item["answer"])
            st.caption(f"{item['category']} · {'공개' if item.get('is_active') else '비공개'} · 순서 {item.get('display_order', 999)}")
            with st.expander("수정·삭제"):
                with st.form(f"api-admin-faq-edit-{item['id']}"):
                    category = st.selectbox("분야 수정", list(CATEGORIES), index=list(CATEGORIES).index(item["category"]), key=f"api-faq-category-{item['id']}")
                    question = st.text_input("질문 수정", value=item["question"], key=f"api-faq-question-{item['id']}")
                    answer = st.text_area("답변 수정", value=item["answer"], key=f"api-faq-answer-{item['id']}")
                    active = st.checkbox("공개", value=item.get("is_active", True), key=f"api-faq-active-{item['id']}")
                    pinned = st.checkbox("상단 고정", value=item.get("is_pinned", False), key=f"api-faq-pinned-{item['id']}")
                    order = st.number_input("표시 순서", min_value=0, value=item.get("display_order", 999), key=f"api-faq-order-{item['id']}")
                    if st.form_submit_button("수정 저장"):
                        try:
                            backend_client.update_admin_faq(token, item["id"], _body(category, question, answer, active, pinned, int(order)))
                            st.rerun()
                        except backend_client.BackendClientError as error:
                            st.error(error.user_message)
                if st.button("FAQ 삭제", key=f"api-faq-delete-{item['id']}"):
                    try:
                        backend_client.delete_admin_faq(token, item["id"])
                        st.rerun()
                    except backend_client.BackendClientError as error:
                        st.error(error.user_message)
