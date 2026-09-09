import streamlit as st

from frontend.clients import backend_client as api


def render_result_save(result, *, kind, result_id):
    token = st.session_state.get("auth_token")
    if not token:
        return
    if result.get("saved") is True:
        st.caption("저장 완료 · 질의 이력에서 확인할 수 있습니다.")
        return
    label = "이 분석 저장하기" if kind == "analysis" else "이 대화를 저장하기"
    if st.button(label, key=f"saved-action-{kind}-{result_id}", disabled=not result_id):
        try:
            with st.spinner("저장하고 있습니다."):
                saved = api.save_completed_result(token, result_id, kind=kind)
            result.update(saved)
            st.rerun()
        except api.BackendClientError as error:
            st.error(error.user_message)
    if not result_id:
        st.caption("결과 식별자가 없어 저장할 수 없습니다. 새로 분석해 주세요.")
