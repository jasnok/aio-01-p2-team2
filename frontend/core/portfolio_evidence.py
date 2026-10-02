"""Numeric portfolio evidence; no questions, credentials, or document content."""
from pathlib import Path
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, FiniteFloat, model_validator

Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class DatabaseProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    documents: int = Field(strict=True, ge=0)
    chunks: int = Field(strict=True, ge=0)
    postgres_version_num: int = Field(strict=True, gt=0)
    revision_declared: str
    immutable_snapshot: Literal[False] = False


class MeasurementProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    started_at: AwareDatetime
    finished_at: AwareDatetime
    git_head: str | None = Field(pattern=r"^[a-f0-9]{40}$")
    working_tree_dirty: bool | None = Field(strict=True)
    python: str
    platform: str
    packages: dict[Literal["openai", "httpx", "psycopg", "pgvector"], str]
    constraints_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    code_sha256: dict[str, Digest] = Field(min_length=1)
    code_unchanged_during_measurement: Literal[True]
    database_before: DatabaseProfile | None = None
    database_after: DatabaseProfile | None = None
    database_counts_unchanged: Literal[True] | None = None

    @model_validator(mode="after")
    def check_interval_and_database(self):
        if self.finished_at < self.started_at:
            raise ValueError("Invalid measurement interval")
        if self.database_before is not None or self.database_after is not None:
            if self.database_before != self.database_after or self.database_counts_unchanged is not True:
                raise ValueError("Database profile changed or is incomplete")
        return self


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
    provenance: dict[Literal["embedding", "keyword"], MeasurementProvenance] = Field(default_factory=dict)


DEFAULT_PATH = Path(__file__).resolve().parents[1] / "data" / "portfolio-evidence.json"


def load_evidence(path=DEFAULT_PATH):
    return PortfolioEvidence.model_validate_json(Path(path).read_text(encoding="utf-8"))
