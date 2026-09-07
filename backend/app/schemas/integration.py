from typing import Literal

from pydantic import BaseModel


class McpStatusResponse(BaseModel):
    status: Literal["ok"] = "ok"
    server: str
    url: str
    initialized: bool = True
    tools: list[str]
    tool_count: int



