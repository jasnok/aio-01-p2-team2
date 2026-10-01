from tests.portfolio_quality_dataset import quality_dataset


def test_quality_dataset_has_unique_cases_and_no_invented_semantic_labels():
    rows = quality_dataset()
    assert len(rows) == len({r["id"] for r in rows}) == 60
    assert set(r["split"] for r in rows) == {"development", "holdout"}
    assert all(not r["expected_document_ids"] for r in rows if r["kind"] != "identifier")
    assert all(r["expected_behavior"] == "human_review_pending" for r in rows)
