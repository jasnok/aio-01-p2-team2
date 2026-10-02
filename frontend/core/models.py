from datetime import date
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field


TermText = Annotated[str, Field(strict=True, min_length=1)]


class LegalTermView(BaseModel):
    term: TermText
    description: TermText


class TermSearchView(BaseModel):
    items: list[LegalTermView]


class CategoryTermsView(BaseModel):
    category: Literal['housing', 'labor', 'consumer']
    terms: list[tuple[TermText, TermText]]


class SourceView(BaseModel):
    source_id: str
    title: str
    source_type: Literal["law", "case", "consultation", "external"]
    url: str


class EvidenceView(BaseModel):
    evidence_id: str
    document_id: str
    title: str
    content: str
    source: SourceView
    score: float | None = Field(default=None, ge=0, le=1)
    summary: str | None = None
    law_name: str | None = None
    article_number: str | None = None
    case_number: str | None = None
    case_name: str | None = None
    court: str | None = None
    decided_at: date | None = None
    judgment_result: str | None = None
    similar_points: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResultsView(BaseModel):
    request_id: str = Field(min_length=1)
    query: str
    category: Literal["housing", "labor", "consumer"]
    items: list[EvidenceView]
    total: int = Field(ge=0)
    is_mock: bool


class InputChecklistView(BaseModel):
    situation: Literal["met", "missing", "not_required"]
    timing: Literal["met", "missing", "not_required"]
    relationship: Literal["met", "missing", "not_required"]
    request_evidence: Literal["met", "missing", "not_required"]


class InputAssessmentView(BaseModel):
    status: Literal["sufficient", "proceed_with_caution", "needs_clarification"]
    message: str = Field(strict=True)
    checks: InputChecklistView | None = None


class ClaimCitationView(BaseModel):
    evidence_id: str = Field(strict=True, min_length=1)
    quote: str = Field(strict=True, min_length=1, max_length=2400)


class CitedClaimView(BaseModel):
    text: str = Field(strict=True, min_length=1)
    citations: list[ClaimCitationView] = Field(min_length=1)


class LegalQuestionView(BaseModel):
    request_id: str
    agent_id: Literal["housing", "labor", "consumer"]
    status: Literal["completed", "failed", "stopped"]
    termination_reason: str
    question_summary: str
    key_issues: list[str] = Field(default_factory=list)
    answer: str
    input_assessment: InputAssessmentView | None = None
    related_laws: list[EvidenceView] = Field(default_factory=list)
    similar_cases: list[EvidenceView] = Field(default_factory=list)
    consultations: list[EvidenceView] = Field(default_factory=list)
    sources: list[SourceView] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    cautions: list[str] = Field(default_factory=list)
    is_mock: bool = False
    saved: bool | None = Field(default=None, strict=True)
    conversation_id: str | int | None = None
    storage: Literal["member", "guest_temporary", "none"] | None = None
    expires_at: str | None = None
    generation_status: Literal["llm", "fallback", "no_evidence", "clarification", "mock"] = "mock"
    used_evidence_ids: list[str] = Field(default_factory=list)
    cited_claims: list[CitedClaimView] = Field(default_factory=list)
    diagnostics: dict[str, Any] = Field(default_factory=dict)

