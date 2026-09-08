from uuid import uuid4

import streamlit as st

from frontend.clients import backend_client as api
from frontend.clients.agent_stream import receive_run
from frontend.services.api_legal_service import ApiLegalService


def friendly_event(event, data):
    terminal = {
        "run.started": "질문을 확인하고 관련 자료를 찾아보겠습니다.",
        "input.required": "더 정확한 안내를 위해 몇 가지 정보를 알려주세요.",
        "run.completed": "자료 정리가 끝났습니다. 분석 결과를 확인해 주세요.",
        "run.failed": "분석을 마치지 못했습니다. 잠시 후 다시 시도해 주세요.",
    }
    if event in terminal:
        return terminal[event]
    subject = {
        "search_laws": "관련 법령",
        "search_cases": "비슷한 법원 판례",
        "search_consultations": "참고할 상담사례",
        "search_legal_documents": "관련 법률 자료",
        "get_law_article": "법 조문 상세 내용",
        "get_case_detail": "판례 상세 내용",
    }.get(data.get("tool"))
    if subject:
        if event == "step.completed":
            count = data.get("result_count")
            return f"{subject} 검색을 마쳤습니다." + (f" {count}건을 찾았습니다." if type(count) is int and count >= 0 else "")
        return f"{subject}를 찾고 있습니다."
    phase = {"validation": "질문 내용 확인", "validate": "질문 내용 확인",
             "routing": "질문 분야 확인", "generation": "검색 자료 정리",
             "generate": "검색 자료 정리", "verification": "답변과 근거 확인"}.get(data.get("stage"), "분석 단계")
    return f"{phase}을 진행하고 있습니다." if event == "step.started" else f"{phase}을 마쳤습니다."


def analyze_with_stream(category, question):
    guest_id = st.session_state.current_user["id"]
    token = st.session_state.auth_token
    identity = (guest_id, category, question.strip())
    pending = st.session_state.get("sse_pending")
    if not pending or pending["identity"] != identity or pending.get("finished"):
        pending = {"identity": identity, "key": str(uuid4()), "run_id": None,
                   "last_id": 0, "steps": {}, "finished": False}
        st.session_state.sse_pending = pending
    view = st.empty()
    try:
        if pending["run_id"] is None:
            created = api.create_agent_run(token, guest_id, category, question.strip(), pending["key"])
            run_id = created.get("run_id")
            if not isinstance(run_id, str) or not run_id:
                raise api.BackendClientError("작업 생성 API가 SSE 계약과 다릅니다.", "CONTRACT_MISMATCH")
            pending["run_id"] = run_id

        def render():
            with view.container():
                for step in pending["steps"].values():
                    marker = "✓" if step["done"] else "⟳"
                    st.text(f"{marker} {step['message']}")

        def update(number, event, data):
            pending["last_id"] = number
            key = data.get("step_id") or event
            message = friendly_event(event, data)
            pending["steps"][key] = {"message": message, "done": event not in {"step.started", "run.started"}}
            render()

        render()
        raw = receive_run(token, guest_id, pending["run_id"], pending["last_id"], update)
        pending["finished"] = True
        if raw["agent_id"] != category:
            raise api.BackendClientError("분석 분야가 요청과 다릅니다.", "CONTRACT_MISMATCH")
        return ApiLegalService.adapt_analysis(raw, question)
    except api.BackendClientError as error:
        if error.code == "RUN_FAILED":
            pending["finished"] = True
        raise ValueError(error.user_message) from error
