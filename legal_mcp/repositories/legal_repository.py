"""법률 DB 조회 경계. SQL/pgvector 구현은 이 클래스 뒤에 둡니다."""

from typing import Protocol

from legal_mcp.schemas.tools import Evidence


class LegalRepository(Protocol):
    def search_laws(self, query: str, category: str, top_k: int) -> list[Evidence]: ...

    def search_cases(self, query: str, category: str, top_k: int) -> list[Evidence]: ...

    def get_law_article(self, law_name: str, article_number: str) -> Evidence | None: ...
