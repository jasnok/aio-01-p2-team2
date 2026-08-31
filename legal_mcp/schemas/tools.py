from typing import Any, Literal

from pydantic import BaseModel, Field


Category = Literal["housing", "labor", "consumer"]
DocumentType = Literal["LAW", "CASE", "GUIDELINE"]


class SearchLegalDocumentsInput(BaseModel):
    query: str = Field(min_length=5, max_length=2000)
    category: Category
    document_types: list[DocumentType] = Field(default_factory=lambda: ["LAW", "CASE"])
    top_k: int = Field(default=3, ge=1, le=5)


class ToolResponse(BaseModel):
    success: bool
    data: dict[str, Any] | None = None
    meta: dict[str, Any] = Field(default_factory=dict)
    error: dict[str, Any] | None = None

