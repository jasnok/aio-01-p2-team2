from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field


Category = Literal["housing", "labor", "consumer"]
DocumentType = Literal["LAW", "CASE", "GUIDELINE"]


class SearchLegalDocumentsInput(BaseModel):
    query: str = Field(min_length=5, max_length=2000)
    category: Category
    document_types: list[DocumentType] = Field(default_factory=lambda: ["LAW", "CASE"])
    top_k: int = Field(default=3, ge=1, le=3)


class SearchInput(BaseModel):
    query: str = Field(min_length=5, max_length=2000)
    category: Category
    top_k: int = Field(default=3, ge=1, le=3)


class LawArticleInput(BaseModel):
    law_name: str = Field(min_length=1, max_length=200)
    article_number: str = Field(min_length=1, max_length=50)


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


class ToolResult(BaseModel):
    success: bool
    tool: str
    data: list[Evidence] | Evidence | None = None
    error_code: str | None = None
    message: str | None = None


class ToolResponse(BaseModel):
    success: bool
    data: dict[str, Any] | None = None
    meta: dict[str, Any] = Field(default_factory=dict)
    error: dict[str, Any] | None = None
