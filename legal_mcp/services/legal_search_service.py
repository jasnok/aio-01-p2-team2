"""법률 검색 흐름을 담당하는 Service."""

from legal_mcp.core.config import get_settings
from legal_mcp.providers.embedding_provider import create_embedding
from legal_mcp.repositories.legal_repository import LegalRepository


class LegalSearchService:
    def __init__(self) -> None:
        self.repository = LegalRepository()
        self.settings = get_settings()

    def _hybrid_search(
        self,
        query: str,
        category: str,
        document_types: list[str],
        top_k: int,
    ) -> list[dict]:
        """Vector Search와 Keyword Search를 결합한다."""

        if not query.strip():
            raise ValueError("검색어는 비어 있을 수 없습니다.")

        query_embedding = create_embedding(query)

        # 최종 top_k보다 넓게 가져온 뒤 Service에서 재정렬한다.
        candidate_limit = max(top_k * 3, self.settings.retrieval_top_k)

        document_type_set = set(document_types)

        if document_type_set == {"LAW"}:
            vector_rows = self.repository.search_laws(
                embedding=query_embedding,
                category=category,
                limit=candidate_limit,
            )

        elif document_type_set == {"CASE"}:
            vector_rows = self.repository.search_cases(
                embedding=query_embedding,
                category=category,
                limit=candidate_limit,
            )

        else:
            vector_rows = self.repository.search_legal_documents(
                embedding=query_embedding,
                category=category,
                document_types=document_types,
                limit=candidate_limit,
            )

        keyword_rows = self.repository.search_documents_by_keyword(
            query=query,
            category=category,
            document_types=document_types,
            limit=candidate_limit,
        )

        return self._merge_search_results(
            vector_rows=vector_rows,
            keyword_rows=keyword_rows,
            top_k=top_k,
        )

    def _merge_search_results(
        self,
        vector_rows: list[dict],
        keyword_rows: list[dict],
        top_k: int,
    ) -> list[dict]:
        """document_id 기준으로 중복을 제거하고 Hybrid Score를 계산한다."""

        merged: dict[int, dict] = {}

        for row in vector_rows:
            document_id = row["document_id"]
            item = dict(row)

            vector_score = max(
                0.0,
                min(1.0, float(item.get("similarity") or 0.0)),
            )

            item["vector_score"] = vector_score
            item["keyword_score"] = 0.0
            merged[document_id] = item

        for row in keyword_rows:
            document_id = row["document_id"]
            keyword_score = max(
                0.0,
                min(1.0, float(row.get("keyword_score") or 0.0)),
            )

            if document_id not in merged:
                item = dict(row)
                item["vector_score"] = 0.0
                item["keyword_score"] = keyword_score
                merged[document_id] = item
            else:
                merged[document_id]["keyword_score"] = keyword_score

        results = []

        for item in merged.values():
            hybrid_score = (
                item["vector_score"] * self.settings.vector_weight
                + item["keyword_score"] * self.settings.keyword_weight
            )

            item["similarity"] = round(hybrid_score, 4)
            item["retrieval_method"] = "hybrid"
            results.append(item)

        results.sort(
            key=lambda item: item["similarity"],
            reverse=True,
        )

        return results[:top_k]

    def search_laws(
        self,
        query: str,
        category: str,
        top_k: int = 3,
    ) -> list[dict]:
        """법령만 Hybrid Search한다."""

        return self._hybrid_search(
            query=query,
            category=category,
            document_types=["LAW"],
            top_k=top_k,
        )

    def search_cases(
        self,
        query: str,
        category: str,
        top_k: int = 3,
    ) -> list[dict]:
        """판례만 Hybrid Search한다."""

        return self._hybrid_search(
            query=query,
            category=category,
            document_types=["CASE"],
            top_k=top_k,
        )

    def search_legal_documents(
        self,
        query: str,
        category: str,
        document_types: list[str],
        top_k: int = 3,
    ) -> list[dict]:
        """법령과 판례를 Hybrid Search한다."""

        return self._hybrid_search(
            query=query,
            category=category,
            document_types=document_types,
            top_k=top_k,
        )

    def get_case_detail(self, document_id: int) -> dict | None:
        """판례 ID로 판례 원문 상세 정보를 조회한다."""
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