from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field


class SourceView(BaseModel):
    source_id: str
    title: str
    source_type: Literal["law", "case", "external"]
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


class LegalQuestionView(BaseModel):
    request_id: str
    agent_id: Literal["housing", "labor", "consumer"]
    status: Literal["completed", "failed", "stopped"]
    termination_reason: str
    question_summary: str
    key_issues: list[str] = Field(default_factory=list)
    answer: str
    related_laws: list[EvidenceView] = Field(default_factory=list)
    similar_cases: list[EvidenceView] = Field(default_factory=list)
    sources: list[SourceView] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    cautions: list[str] = Field(default_factory=list)
    is_mock: bool = False

