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
