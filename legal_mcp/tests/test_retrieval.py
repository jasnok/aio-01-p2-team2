from types import SimpleNamespace

from legal_mcp.services.legal_search_service import LegalSearchService
from legal_mcp.services.query_terms import extract_query_terms


def service(threshold=0.0, fusion="weighted"):
    instance = LegalSearchService.__new__(LegalSearchService)
    instance.settings = SimpleNamespace(vector_weight=0.7, keyword_weight=0.3,
        retrieval_score_threshold=threshold, retrieval_fusion=fusion, rrf_k=60,
        retrieval_filter_enabled=True)
    return instance


def test_best_chunk_survives_duplicate_document():
    rows = [{"document_id": 1, "similarity": 0.9, "chunk_content": "best"},
            {"document_id": 1, "similarity": 0.4, "chunk_content": "worse"}]
    result = service()._merge_search_results(rows, [], 3)
    assert result[0]["chunk_content"] == "best"
    assert result[0]["similarity"] == 0.63


def test_keyword_terms_cannot_lower_previous_match():
    rows = [{"document_id": 1, "keyword_score": 1.0},
            {"document_id": 1, "keyword_score": 0.5}]
    result = service()._merge_search_results([], rows, 3)
    assert result[0]["keyword_score"] == 1.0


def test_relevance_gate_removes_weak_hits_in_both_fusion_modes():
    rows = [{"document_id": 1, "similarity": 0.4},
            {"document_id": 2, "similarity": 0.9}]
    for fusion in ("weighted", "rrf"):
        assert [r["document_id"] for r in service(0.5, fusion)._merge_search_results(rows, [], 3)] == [2]


def test_rrf_rewards_agreement_without_overwriting_relevance_score():
    rows = [{"document_id": 1, "similarity": 0.9}, {"document_id": 2, "similarity": 0.8}]
    result = service(fusion="rrf")._merge_search_results(rows, [{"document_id": 2, "keyword_score": 0.8}], 3)
    assert result[0]["document_id"] == 2
    assert result[0]["similarity"] == 0.8
    assert result[0]["ranking_score"] < 0.1


def test_query_terms_preserve_identifiers_and_extract_spaced_terms():
    terms = extract_query_terms("퇴직 후 퇴직금을 못 받았습니다. 근로기준법 제 36 조와 2024가합12664를 확인하고 싶어요.")
    assert "퇴직금" in terms
    assert "제36조" in terms
    assert "2024가합12664" in terms
    assert len(terms) <= 8
