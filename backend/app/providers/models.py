from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ProviderResult:
    provider: str
    model: str
    output: Any
    elapsed_ms: int
    usage: dict[str, int] = field(default_factory=dict)
