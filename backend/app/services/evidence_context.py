"""Bounded extractive context. Every span is copied exactly from source text."""
from backend.app.services.text_spans import select_windows
from backend.app.agents.models import AnswerDraft
from backend.app.schemas.legal import Evidence


def build_context(question: str, evidence: list[Evidence], max_documents: int = 6,
                  max_windows: int = 3, document_budget: int = 2400):
    if max_documents < 1:
        raise ValueError("max_documents must be positive")
    ranked = sorted(enumerate(evidence), key=lambda pair: (-(pair[1].score or 0), pair[0]))
    windows = {}

    def extract(index, item):
        if index not in windows:
            windows[index] = select_windows(question, item.content, limit=max_windows, budget=document_budget)
        return windows[index]

    selected = []
    # Preserve source diversity before filling the remaining context budget.
    for source_type in ("law", "case", "consultation", "external"):
        if len(selected) >= max_documents:
            break
        match = next(((index, item) for index, item in ranked
                      if item.source.source_type == source_type and extract(index, item)), None)
        if match:
            selected.append(match)
    for index, item in ranked:
        if len(selected) >= max_documents:
            break
        if item.evidence_id not in {doc.evidence_id for _, doc in selected} and extract(index, item):
            selected.append((index, item))
    documents, spans = [], {}
    for index, item in selected:
        excerpts = []
        for window in windows[index]:
            span_id = f"{item.evidence_id}:{window['source_sha256'][:12]}:{window['start']}:{window['end']}"
            spans[span_id] = {"evidence_id": item.evidence_id, **window}
            excerpts.append({"span_id": span_id, "text": window["quote"]})
        if excerpts:
            documents.append({"evidence_id": item.evidence_id, "title": item.title,
                              "source_type": item.source.source_type, "excerpts": excerpts})
    return documents, spans


def resolve_span_draft(output: dict, spans: dict) -> AnswerDraft:
    from backend.app.agents.models import SpanAnswerDraft
    generated = SpanAnswerDraft.model_validate(output)
    claims = []
    for claim in generated.claims:
        citations = []
        for span_id in dict.fromkeys(claim.span_ids):
            if span_id not in spans:
                raise ValueError("unknown_citation_span")
            citations.append({key: spans[span_id][key] for key in ("evidence_id", "quote")})
        claims.append({"text": claim.text, "citations": citations})
    # Bind the displayed answer to the same claims that carry citations.
    # The model cannot add an uncited parallel answer field.
    return AnswerDraft(question_summary=generated.question_summary,
        answer="\n\n".join(claim.text for claim in generated.claims),
        key_issues=generated.key_issues, cautions=generated.cautions, claims=claims,
        used_evidence_ids=list(dict.fromkeys(citation["evidence_id"]
            for claim in claims for citation in claim["citations"])))
