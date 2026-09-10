from typing import Literal

from pydantic import BaseModel, Field


class LegalTermChatRequest(BaseModel):
    message: str = Field(min_length=2, max_length=1000)
    conversation_id: int | None = Field(default=None, gt=0)
    save_selected: bool = False


class LegalTermLLMOutput(BaseModel):
    is_legal_term_question: bool
    answer: str = Field(min_length=1, max_length=2000)
    related_terms: list[str] = Field(default_factory=list, max_length=3)
    caution: str = Field(min_length=1, max_length=300)


class LegalTermChatResponse(BaseModel):
    request_id: str
    answer: str
    related_terms: list[str] = Field(default_factory=list)
    notice: str
    conversation_id: int | None = None
    saved: bool = False
    storage: Literal["member", "guest_temporary", "none"]
    is_llm_response: bool
