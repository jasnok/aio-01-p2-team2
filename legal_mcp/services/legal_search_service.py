"""법률 검색 흐름을 담당하는 Service."""

import hashlib
import json
from legal_mcp.core.cache import QueryCache
from legal_mcp.core.config import get_settings
from legal_mcp.providers.embedding_provider import create_embedding
from legal_mcp.repositories.legal_repository import LegalRepository
from legal_mcp.services.query_terms import extract_query_terms

_result_cache = QueryCache()


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
        """Cache public retrieval only; never cache user answers or histories."""
        config = self.settings.model_dump()
        # Hash the entire retrieval configuration so model, credentials, DB,
        # weights, relevance gate and dataset revision cannot share an entry.
        key = hashlib.sha256(json.dumps([query, category, sorted(document_types), top_k, config],
                              sort_keys=True, default=str).encode()).digest()
        return _result_cache.get_or_load(key,
            lambda: self._hybrid_search_uncached(query, category, document_types, top_k),
            ttl=self.settings.retrieval_cache_ttl_seconds)

    def _hybrid_search_uncached(self, query, category, document_types, top_k):
        """Vector Search와 Keyword Search를 결합한다."""

        if not query.strip():
            raise ValueError("검색어는 비어 있을 수 없습니다.")

        query_embedding = create_embedding(query)

        # 최종 top_k보다 넓게 가져온 뒤 Service에서 재정렬한다.
        candidate_limit = max(top_k * 3, self.settings.retrieval_top_k)

        vector_rows, keyword_rows = self.repository.search_hybrid_candidates(
            embedding=query_embedding,
            queries=extract_query_terms(query),
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
            previous = merged.get(document_id)
            if previous is None or vector_score > previous["vector_score"]:
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
                merged[document_id]["keyword_score"] = max(
                    merged[document_id]["keyword_score"], keyword_score
                )

        results = []

        vector_ranks = {
            item["document_id"]: rank
            for rank, item in enumerate(sorted(
                (item for item in merged.values() if item["vector_score"] > 0),
                key=lambda item: (-item["vector_score"], str(item["document_id"])),
            ), 1)
        }
        keyword_ranks = {
            item["document_id"]: rank
            for rank, item in enumerate(sorted(
                (item for item in merged.values() if item["keyword_score"] > 0),
                key=lambda item: (-item["keyword_score"], str(item["document_id"])),
            ), 1)
        }
        for item in merged.values():
            hybrid_score = (
                item["vector_score"] * self.settings.vector_weight
                + item["keyword_score"] * self.settings.keyword_weight
            )

            # Relevance gate uses the weighted score in both modes. RRF is a
            # ranking score, never a calibrated relevance probability.
            if self.settings.retrieval_filter_enabled and hybrid_score < self.settings.retrieval_score_threshold:
                continue
            item["similarity"] = round(hybrid_score, 4)
            if self.settings.retrieval_fusion == "rrf":
                item["ranking_score"] = sum(
                    1 / (self.settings.rrf_k + ranks[item["document_id"]])
                    for ranks in (vector_ranks, keyword_ranks)
                    if item["document_id"] in ranks
                )
            else:
                item["ranking_score"] = hybrid_score
            item["retrieval_method"] = "hybrid"
            results.append(item)

        results.sort(
            key=lambda item: item["ranking_score"],
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

    def search_consultations(
        self,
        query: str,
        category: str,
        top_k: int = 3,
    ) -> list[dict]:
        """공식 상담·해석 사례를 Hybrid Search한다."""

        return self._hybrid_search(
            query=query,
            category=category,
            document_types=["CONSULTATION"],
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
