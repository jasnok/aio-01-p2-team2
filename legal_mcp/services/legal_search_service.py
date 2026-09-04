"""MCP Tool과 Repository 사이의 검색 규칙을 담당합니다."""

from legal_mcp.repositories.legal_repository import LegalRepository
from legal_mcp.schemas.tools import Evidence


class LegalSearchService:
    def __init__(self, repository: LegalRepository):
        self.repository = repository

    def search_laws(self, query: str, category: str, top_k: int = 3) -> list[Evidence]:
        return self.repository.search_laws(query, category, min(top_k, 3))

    def search_cases(self, query: str, category: str, top_k: int = 3) -> list[Evidence]:
        return self.repository.search_cases(query, category, min(top_k, 3))

    def get_law_article(self, law_name: str, article_number: str) -> Evidence | None:
        return self.repository.get_law_article(law_name, article_number)
