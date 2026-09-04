from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field


Category = Literal["housing", "labor", "consumer"]


class LegalQuestionRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)
    category: Category
    question: str = Field(min_length=5, max_length=2000)


class Source(BaseModel):
    source_id: str
    title: str
    source_type: Literal["law", "case", "external"]
    url: str


class Evidence(BaseModel):
    evidence_id: str
    document_id: str
    title: str
    content: str
    source: Source
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


class LegalQuestionResponse(BaseModel):
    request_id: str
    agent_id: Category
    status: Literal["completed", "failed", "stopped"] = "completed"
    termination_reason: str
    question_summary: str
    key_issues: list[str] = Field(default_factory=list)
    answer: str
    related_laws: list[Evidence] = Field(default_factory=list)
    similar_cases: list[Evidence] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    cautions: list[str] = Field(default_factory=list)
    is_mock: bool = True
