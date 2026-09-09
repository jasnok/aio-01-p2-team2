"""Display backend assessments only; never infer requirements from input text."""

import streamlit as st


LABELS = {
    "situation": "구체적인 상황",
    "timing": "시점·기간",
    "relationship": "상대방·관계",
    "request_evidence": "요청·증거",
}


def render_input_checklist(category: str, message: str, result: dict | None) -> None:
    if not result:
        st.caption("입력 체크리스트: 사례 분석을 요청하면 Agent가 필요한 정보를 확인합니다.")
        return
    if result.get("agent_id") != category or result.get("question", "").strip() != message.strip():
        st.caption("질문이 변경되었습니다. 다시 분석하면 입력 체크리스트가 갱신됩니다.")
        return
    assessment = result.get("input_assessment") or {}
    checks = assessment.get("checks")
    if not checks:
        st.caption("백엔드의 항목별 판단 결과가 아직 제공되지 않았습니다.")
        return
    needed = sum(value != "not_required" for value in checks.values())
    met = sum(value == "met" for value in checks.values())
    count = f"확인된 정보 {met}/{needed}"
    if needed < 4:
        count += f" · 해당 없음 {4 - needed}"
    if assessment.get("status") == "needs_clarification":
        title = "추가 정보를 알려주세요"
        tone = "warn"
    elif assessment.get("status") == "proceed_with_caution":
        title = "검색 가능 · 추가 확인할 정보가 있어요"
        tone = "warn"
    else:
        title = "검색을 진행할 수 있는 입력입니다"
        tone = "good"
    marks = {"met": "✓", "missing": "○", "not_required": "—"}
    items = " · ".join(
        f"{marks[checks[key]]} {label}" + (" (해당 없음)" if checks[key] == "not_required" else "")
        for key, label in LABELS.items()
    )
    # HTML contains only fixed labels and counts, never backend/user free text.
    st.markdown(
        f'<div class="input-quality {tone}"><strong>{title} ({count})</strong><br><span>{items}</span></div>',
        unsafe_allow_html=True,
    )
    st.caption("Agent의 제출 질문 기준 판단입니다. ○는 추가 확인이 필요한 정보이며, 모든 항목이 검색 필수조건은 아닙니다.")
