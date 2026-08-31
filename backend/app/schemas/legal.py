from typing import Literal

from pydantic import BaseModel, Field


Category = Literal["housing", "labor", "consumer"]


class LegalQuestionRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)
    category: Category
    message: str = Field(min_length=5, max_length=2000)


class LegalDocument(BaseModel):
    document_id: str
    document_type: Literal["LAW", "CASE", "GUIDELINE"]
    category: Category
    title: str
    summary: str
    content: str
    source_name: str
    source_url: str | None = None
    effective_date: str | None = None
    score: float
    metadata: dict = Field(default_factory=dict)


class LegalQuestionResponse(BaseModel):
    request_id: str
    status: Literal["completed"] = "completed"
    category: Category
    question_summary: str
    answer: str
    laws: list[LegalDocument] = Field(default_factory=list)
    cases: list[LegalDocument] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    disclaimer: str
    trace: list[dict] = Field(default_factory=list)
    is_mock: bool = True

