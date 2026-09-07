from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class NormalizedLegalDocument(BaseModel):
    # 원본 데이터를 식별하는 고유 ID입니다.
    # 소비자원 데이터는 예를 들어 kca-relief-1 형태로 만듭니다.
    external_id: str

    # LAW: 법령
    # CASE: 법원 판례
    # ADMIN_DECISION: 노동위원회 판정례
    # CONSULTATION: 소비자 피해구제 사례
    document_type: Literal[
        "LAW",
        "CASE",
        "GUIDELINE",
        "ADMIN_DECISION",
        "CONSULTATION",
    ]

    # 프로젝트에서 사용하는 법률 분야입니다.
    category: Literal[
        "housing",
        "labor",
        "consumer",
    ]

    # 검색 결과 카드에 표시할 제목입니다.
    title: str

    # 실제 RAG 검색에 사용할 전체 본문입니다.
    content: str

    # 데이터 제공기관 이름입니다.
    source_name: str

    # 사용자에게 보여줄 공식 출처 URL입니다.
    source_url: str

    # file: CSV/XML
    # api: 외부 API
    # seed: 공식 출처에서 선별한 테스트 자료
    source_type: Literal["file", "api", "seed"]

    # 해당 문서가 만들어진 원본 파일입니다.
    raw_file: str | None = None

    # 본문 변경 여부를 확인하는 SHA-256 값입니다.
    content_hash: str

    law_name: str | None = None
    article_number: str | None = None

    case_number: str | None = None
    case_name: str | None = None
    court: str | None = None
    decided_at: date | None = None
    judgment_result: str | None = None

    summary: str | None = None
    effective_date: date | None = None
    source_updated_at: datetime | None = None

    # 원본에만 있는 부가 필드를 JSON 형태로 저장합니다.
    metadata: dict[str, Any] = Field(default_factory=dict)


class LegalChunk(BaseModel):
    # 하나의 문서 안에서 Chunk 순서입니다.
    chunk_index: int = Field(ge=0)

    # question_answer, article, holding 등 Chunk 종류입니다.
    section_type: str | None = None

    # 실제 Embedding을 생성할 텍스트입니다.
    content: str

    # 토큰 수를 계산했다면 저장합니다.
    token_count: int | None = Field(default=None, ge=0)

    # Chunk 본문의 SHA-256 값입니다.
    content_hash: str

    # DB 적재와 질문 검색에 동일한 모델을 사용해야 합니다.
    embedding_model: str = "text-embedding-3-small"
    embedding_version: str = "v1"