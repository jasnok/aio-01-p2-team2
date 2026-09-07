"""법률 검색 흐름을 담당하는 Service."""

from legal_mcp.providers.embedding_provider import create_embedding
from legal_mcp.repositories.legal_repository import LegalRepository


class LegalSearchService:
    def __init__(self) -> None:
        self.repository = LegalRepository()

    def search_cases(
        self,
        query: str,
        category: str,
        top_k: int = 3,
    ) -> list[dict]:
        """사용자 질의와 유사한 판례를 검색한다."""

        if not query.strip():
            raise ValueError("검색어는 비어 있을 수 없습니다.")

        if not category.strip():
            raise ValueError("category는 비어 있을 수 없습니다.")

        query_embedding = create_embedding(query)

        return self.repository.search_cases(
            embedding=query_embedding,
            category=category,
            limit=top_k,
        )
    
    def get_case_detail(self, document_id: int) -> dict | None:
        """판례 ID로 원문 상세 정보를 조회한다."""
        return self.repository.get_case_detail(document_id)

    def get_law_article(
        self,
        law_name: str,
        article_number: str,
    ) -> dict | None:
        """특정 법령 조문을 조회한다."""
        return self.repository.get_law_article(
            law_name=law_name,
            article_number=article_number,
        )

    def search_legal_documents(
        self,
        query: str,
        category: str,
        document_types: list[str],
        top_k: int = 3,
    ) -> list[dict]:
        """법령과 판례를 통합 벡터 검색한다."""

        if not query.strip():
            raise ValueError("검색어는 비어 있을 수 없습니다.")

        query_embedding = create_embedding(query)

        return self.repository.search_legal_documents(
            embedding=query_embedding,
            category=category,
            document_types=document_types,
            limit=top_k,
        )