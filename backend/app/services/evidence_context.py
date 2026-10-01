"""Bounded extractive context. Every span is copied exactly from source text."""
import re
from backend.app.agents.models import AnswerDraft
from backend.app.schemas.legal import Evidence


def build_context(question: str, evidence: list[Evidence], max_documents: int = 6):
    if max_documents < 1:
        raise ValueError("max_documents must be positive")
    ranked = sorted(enumerate(evidence), key=lambda pair: (-(pair[1].score or 0), pair[0]))
    selected = []
    # Preserve source diversity before filling the remaining context budget.
    for source_type in ("law", "case", "consultation", "external"):
        match = next((item for _, item in ranked if item.source.source_type == source_type), None)
        if match and len(selected) < max_documents:
            selected.append(match)
    for _, item in ranked:
        if len(selected) >= max_documents:
            break
        if item.evidence_id not in {doc.evidence_id for doc in selected}:
            selected.append(item)
    terms = set(re.findall(r"[가-힣A-Za-z0-9]{2,}", question))
    # Character pairs provide a deterministic Korean lexical signal without
    # assuming that spacing or inflected word endings match exactly.
    pairs = {term[index:index+2] for term in terms for index in range(len(term)-1)}
    documents, spans = [], {}
    for item in selected:
        fragments = []
        for sentence in re.split(r"(?<=[.!?。])\s+|\n+", item.content):
            sentence = sentence.strip()
            for offset in range(0, len(sentence), 280):
                fragment = sentence[offset:offset+280]
                if fragment.strip():
                    fragments.append(fragment)
        scored = sorted(enumerate(fragments), key=lambda pair: (
            -sum(token in pair[1] for token in pairs), pair[0]))
        chosen = sorted(scored[:3], key=lambda pair: pair[0])
        excerpts = []
        for index, quote in chosen:
            span_id = f"{item.evidence_id}:s{index+1}"
            spans[span_id] = {"evidence_id": item.evidence_id, "quote": quote}
            excerpts.append({"span_id": span_id, "text": quote})
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
            citations.append(dict(spans[span_id]))
        claims.append({"text": claim.text, "citations": citations})
    # Bind the displayed answer to the same claims that carry citations.
    # The model cannot add an uncited parallel answer field.
    return AnswerDraft(question_summary=generated.question_summary,
        answer="\n\n".join(claim.text for claim in generated.claims),
        key_issues=generated.key_issues, cautions=generated.cautions, claims=claims,
        used_evidence_ids=list(dict.fromkeys(citation["evidence_id"]
            for claim in claims for citation in claim["citations"])))
