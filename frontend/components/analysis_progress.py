import streamlit as st

from frontend.core.workflow import WORKFLOW_STEPS


def render_analysis_progress(active_step: str | None = None, *, completed: bool = False) -> None:
    st.markdown("#### ⚙ Agent 진행 상태")
    columns = st.columns(len(WORKFLOW_STEPS))
    active_index = next((index for index, (code, _) in enumerate(WORKFLOW_STEPS) if code == active_step), -1)
    for index, (code, label) in enumerate(WORKFLOW_STEPS):
        if completed or index < active_index:
            marker = "✅"
        elif index == active_index:
            marker = "🔄"
        else:
            marker = "○"
        columns[index].markdown(f'<div class="workflow-step"><span>{marker}</span><small>{label}</small></div>', unsafe_allow_html=True)


def render_workflow_run(scenario: str = "success") -> None:
    failure_step = {
        "backend_error": "validate",
        "mcp_error": "search_cases",
        "db_error": "search_laws",
        "timeout": "generate",
        "invalid_response": "generate",
        "cancelled": "route",
    }.get(scenario)
    with st.status("Agent가 사례를 분석하고 있습니다.", expanded=True) as status:
        for code, label in WORKFLOW_STEPS:
            if code == failure_step:
                st.write(f"⚠️ {label}")
                status.update(label="분석을 완료하지 못했습니다.", state="error", expanded=True)
                return
            st.write(f"✅ {label}")
        status.update(label="분석이 완료되었습니다.", state="complete", expanded=False)


def render_analysis_error(error: dict) -> None:
    st.error(f"**{error['stage']} 단계에서 문제가 발생했습니다.**  \n{error['message']}")
    st.info(f"다음 행동: {error['next_action']}")
    st.caption(f"오류 코드: {error['code']} · {'다시 시도 가능' if error['retryable'] else '확인 필요'}")
