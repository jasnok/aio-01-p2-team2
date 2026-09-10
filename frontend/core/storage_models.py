"""Contracts for account, saved results and conversation screens."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr

from frontend.core.models import LegalQuestionView

Identifier = StrictInt | StrictStr


class UserView(BaseModel):
    id: Identifier
    email: str | None = None
    display_name: str
    role: Literal["USER", "ADMIN", "GUEST"]


class LoginView(BaseModel):
    access_token: StrictStr = Field(min_length=1)
    expires_in: int | None = Field(default=None, gt=0)
    user: UserView


class MessageView(BaseModel):
    role: Literal["user", "assistant"]
    content: StrictStr
    created_at: datetime | None = None


class HistoryItemView(BaseModel):
    id: Identifier
    type: Literal["analysis", "legal_terms"]
    title: str = ""
    question: str = ""
    summary: str = ""
    created_at: datetime | None = None
    expires_at: datetime | None = None
    result: LegalQuestionView | None = None
    messages: list[MessageView] = Field(default_factory=list)


class HistoryPageView(BaseModel):
    items: list[HistoryItemView]
    total: int | None = Field(default=None, ge=0)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1)
    expires_at: datetime | None = None
    expires_in: int | None = Field(default=None, ge=0)
    notice: str = ""


class TermReplyView(BaseModel):
    request_id: StrictStr = Field(min_length=1)
    answer: StrictStr = Field(min_length=1)
    conversation_id: Identifier | None = None
    saved: StrictBool = False
    storage: Literal["member", "guest_temporary", "none"] = "none"
    expires_at: datetime | None = None
    notice: str = ""
    model_config = ConfigDict(extra="ignore")


class SaveResultView(BaseModel):
    saved: StrictBool
    conversation_id: StrictInt = Field(gt=0)
