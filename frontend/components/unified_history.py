import streamlit as st

from frontend.core.session import restore_history_item


def render_unified_history() -> None:
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
                st.write(item["content"])
                if item.get("answer"):
                    st.write(item["answer"])
