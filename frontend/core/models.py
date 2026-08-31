from typing import Any, Literal

from pydantic import BaseModel, Field


class LegalDocumentView(BaseModel):
    document_id: str
    document_type: Literal["LAW", "CASE", "GUIDELINE"]
    category: Literal["housing", "labor", "consumer"]
    title: str
    summary: str
    content: str
    source_name: str
    source_url: str | None = None
    effective_date: str | None = None
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class LegalQuestionView(BaseModel):
    request_id: str
    status: Literal["completed"]
    category: Literal["housing", "labor", "consumer"]
    question_summary: str
    answer: str
    laws: list[LegalDocumentView] = Field(default_factory=list)
    cases: list[LegalDocumentView] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    disclaimer: str
    trace: list[dict[str, Any]] = Field(default_factory=list)
    is_mock: bool = False

