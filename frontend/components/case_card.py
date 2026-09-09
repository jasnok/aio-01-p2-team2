from frontend.components.evidence_card import render_evidence_card


def render_case_card(case: dict, index: int) -> None:
    render_evidence_card(case, index, "case")
