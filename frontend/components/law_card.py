from frontend.components.evidence_card import preview, render_evidence_card


def law_preview(law: dict) -> str:
    return preview(str(law.get("summary") or law.get("content") or law.get("detail") or "내용이 없습니다."))


def render_law_card(law: dict, index: int) -> None:
    render_evidence_card(law, index, "law")
