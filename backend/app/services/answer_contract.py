"""Pure citation and final-claim rules shared by both answer formats."""
from dataclasses import dataclass, field
import re
import unicodedata
from backend.app.agents.models import AnswerDraft, AnswerReview
from backend.app.schemas.legal import Evidence


class CitationValidationError(ValueError):
    """Static reasons only; never include source/model text."""


@dataclass
class AnswerContext:
    message: str
    documents: list[dict]
    spans: dict[str, dict]
    span_mode: bool


@dataclass
class GenerationOutcome:
    draft: AnswerDraft
    llm_used: bool = False
    diagnostics: dict = field(default_factory=dict)


def normalize(text):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text))


def citation_ids(draft):
    return list(dict.fromkeys(c.evidence_id for claim in draft.claims for c in claim.citations))


def validate_citations(draft: AnswerDraft, evidence: list[Evidence], span_mode: bool):
    sources = {item.evidence_id: normalize(item.content if span_mode else item.content[:1500])
               for item in evidence}
    if not set(draft.used_evidence_ids).issubset(sources):
        raise CitationValidationError("unknown_evidence")
    if not draft.claims:
        raise CitationValidationError("missing_cited_claims")
    for claim in draft.claims:
        for citation in claim.citations:
            if citation.evidence_id not in sources:
                raise CitationValidationError("unused_claim_evidence")
            quote = normalize(citation.quote)
            if not quote or quote not in sources[citation.evidence_id]:
                raise CitationValidationError("quote_not_in_evidence")
    ids = citation_ids(draft)
    changed = set(ids) != set(draft.used_evidence_ids)
    draft.used_evidence_ids = ids
    return changed


def retain_supported(draft: AnswerDraft, review: AnswerReview):
    approved = sorted(item.claim_index for item in review.claims if item.verdict == "supported")
    if len(approved) == len(draft.claims):
        return draft, approved
    if not approved:
        raise CitationValidationError("no_supported_claims")
    result = draft.model_copy(deep=True)
    result.claims = [draft.claims[index] for index in approved]
    result.answer = "\n\n".join(claim.text for claim in result.claims)
    result.used_evidence_ids = citation_ids(result)
    result.cautions.append("일부 주장은 인용문과의 의미 검토를 통과하지 못해 제외했습니다. 이 검토는 법률 정답을 보장하지 않습니다.")
    return result, approved
