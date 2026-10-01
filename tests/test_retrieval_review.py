import pytest
from scripts.review_retrieval import fingerprint, score


def dataset():
    return {"records": [{"id": "q", "kind": "natural", "query": "질문", "variants": {
        "good": {"document_ids": [1, 2, 3], "titles": ["a", "b", "c"], "chunks": ["a", "b", "c"]},
        "bad": {"document_ids": [3, 2, 1], "titles": ["c", "b", "a"], "chunks": ["c", "b", "a"]}}}]}


def test_unjudged_queries_do_not_become_zero_quality_scores():
    data = dataset()
    result = score(data, {"dataset_fingerprint": fingerprint(data), "reviewer": "검토자", "grades": {}})
    assert result["reviewed_queries"] == 0
    assert result["summary"] == {}


def test_scores_reward_relevant_ranking_and_use_all_candidate_labels():
    data = dataset()
    result = score(data, {"dataset_fingerprint": fingerprint(data), "reviewer": "검토자",
                          "grades": {"q": {"1": 3, "2": 2, "3": 0}}})
    assert result["summary"]["good"]["pooled_ndcg_at_3"] == 1
    assert result["summary"]["bad"]["pooled_ndcg_at_3"] < 1
    assert result["summary"]["good"]["precision_at_3"] == pytest.approx(2/3)


def test_labels_from_other_snapshot_are_rejected():
    with pytest.raises(ValueError, match="다릅니다"):
        score(dataset(), {"dataset_fingerprint": "wrong", "reviewer": "검토자"})
