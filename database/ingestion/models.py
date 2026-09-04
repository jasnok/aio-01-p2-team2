from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class NormalizedLegalDocument(BaseModel):
    external_id: str
    document_type: Literal["LAW", "CASE", "GUIDELINE"]
    category: Literal["housing", "labor", "consumer"]
    title: str
    content: str
    source_name: str
    source_url: str
    content_hash: str
    law_name: str | None = None
    article_number: str | None = None
    case_number: str | None = None
    court: str | None = None
    decided_at: date | None = None
    judgment_result: str | None = None
    summary: str | None = None
    effective_date: date | None = None
    source_updated_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LegalChunk(BaseModel):
    chunk_index: int = Field(ge=0)
    content: str
    token_count: int | None = Field(default=None, ge=0)
