"""Numeric portfolio evidence; no questions, credentials, or document content."""
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat


class EvidenceRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    experiment: Literal["embedding", "keyword"]
    category: Literal["housing", "labor", "consumer"] | None = None
    before_ms: FiniteFloat = Field(ge=0)
    after_ms: FiniteFloat = Field(ge=0)
    samples: int = Field(strict=True, gt=0)
    warmup: int = Field(strict=True, ge=0)
    python: str
    equivalent_pairs: int | None = Field(default=None, strict=True, gt=0)


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class EnvironmentEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    platform: str
    python: str
    packages: int = Field(strict=True, gt=0)
    errors: int = Field(strict=True, ge=0)
    constraints_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class PortfolioEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    rows: list[EvidenceRow] = Field(min_length=1)
    environments: list[EnvironmentEvidence]
    sources: list[Source]


DEFAULT_PATH = Path(__file__).resolve().parents[1] / "data" / "portfolio-evidence.json"


def load_evidence(path=DEFAULT_PATH):
    return PortfolioEvidence.model_validate_json(Path(path).read_text(encoding="utf-8"))
