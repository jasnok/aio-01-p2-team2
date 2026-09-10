from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProviderResult:
    provider: str
    model: str
    output: Any
    elapsed_ms: int
