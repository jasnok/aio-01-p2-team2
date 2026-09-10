"""Select storage for the next request, without sending another API call."""
import streamlit as st


def _toggle(key):
    if st.session_state.get("auth_token"):
        st.session_state[key] = not st.session_state.get(key, False)
    else:
        st.session_state[key] = False
        st.session_state[key + "_login_notice"] = True


def render_save_selection(label, key, *, disabled=False, saved=False):
    selected = bool(st.session_state.get("auth_token") and st.session_state.get(key, False))
    st.button(
        "✓ 저장된 대화" if saved else ("✓ 저장 선택됨 · 해제" if selected else label),
        key=key + "_button", on_click=_toggle, args=(key,),
        type="primary" if selected or saved else "secondary", disabled=disabled or saved,
    )
    if st.session_state.get(key + "_login_notice") and not st.session_state.get("auth_token"):
        st.info("계속 보관하려면 회원가입 또는 로그인이 필요합니다.")
    elif selected and not saved:
        st.caption("다음 요청이 완료되면 저장합니다.")
    return selected
