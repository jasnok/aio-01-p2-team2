"""Agent 실행 계약. 실제 LLM loop 구현은 runtime.py에 추가합니다."""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class AgentProfile:
    agent_id: str
    name: str
    goal: str
    description: str
    example_question: str
    instructions: str
    allowed_tools: frozenset[str]


class AgentState(BaseModel):
    request_id: str
    agent_id: str
    question: str
    status: Literal["running", "completed", "failed", "stopped"] = "running"
    termination_reason: str | None = None
    current_step: int = 0
    llm_calls: int = 0
    tool_calls: int = 0
    evidence_count: int = 0
    trace: list[dict] = Field(default_factory=list)
    answer: str | None = None


CheckStatus = Literal["met", "missing", "not_required"]


class InputChecks(BaseModel):
    """입력 판단 화면에 보여 줄 항목별 상태다. 부분 객체는 허용하지 않는다."""

    situation: CheckStatus
    timing: CheckStatus
    relationship: CheckStatus
    request_evidence: CheckStatus


class IntakeResult(BaseModel):
    is_ready_for_search: bool
    status: Literal["sufficient", "proceed_with_caution", "needs_clarification"]
    message: str
    missing_fields: list[str] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list, max_length=3)
    cautions: list[str] = Field(default_factory=list)
    checks: InputChecks | None = None

class AnswerDraft(BaseModel):
    question_summary: str
    answer: str
    key_issues: list[str] = Field(default_factory=list)
    cautions: list[str] = Field(default_factory=list)
    used_evidence_ids: list[str] = Field(default_factory=list)
