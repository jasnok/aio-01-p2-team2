from hashlib import sha256
import json

import pytest

from scripts.review_latency import answer_origin, create_review


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


@pytest.fixture
def experiment(tmp_path):
    source = tmp_path / "source.json"
    write_json(source, [{"category": "labor", "question": "퇴직금 질문", "run": {"result": {
        "related_laws": [{"evidence_id": "law-1", "title": "근거 제목", "content": "원문 조건과 예외",
                          "source": {"title": "공식 출처", "source_type": "law", "url": "https://example.org"},
                          "metadata": {"private_marker": "PRIVATE"}}],
        "similar_cases": [], "consultations": []}}}])
    rows = []
    for variant in ("baseline", "candidate"):
        filename = f"case-0-{variant}-1.json"
        write_json(tmp_path / filename, {"category": "labor", "question": "퇴직금 질문", "variant": variant,
            "status": "completed", "scope": "answer", "llm_used": True,
            "answer": {"answer": "답변", "claims": []}, "settings": {"model": "PRIVATE"}})
        rows.append({"file": filename, "scenario": 0, "variant": variant})
    index = {"input": str(source), "input_sha256": sha256(source.read_bytes()).hexdigest(), "runs": rows}
    write_json(tmp_path / "index.json", index)
    return tmp_path, source, index


def test_review_includes_original_evidence_without_settings_or_human_labels(experiment):
    folder, source, index = experiment
    assert create_review(folder) == 2
    public = json.loads((folder / "quality-review.json").read_text(encoding="utf-8"))
    assert public["schema_version"] == 2
    assert public["status"] == "pending_human_review"
    for case in public["cases"]:
        assert case["evidence"][0]["content"] == "원문 조건과 예외"
        assert case["answer_origin"] == "generated"
        assert case["reviewer"] is None and case["notes"] is None
        assert all(value is None for value in case["scores"].values())
    text = json.dumps(public)
    assert "PRIVATE" not in text and '"baseline"' not in text and '"candidate"' not in text
    assert {row["variant"] for row in json.loads((folder / "quality-review-key.json").read_text())} == {"baseline", "candidate"}


@pytest.mark.parametrize("existing", ["quality-review.json", "quality-review-key.json"])
def test_existing_human_review_and_key_are_preserved(experiment, existing):
    folder, _, _ = experiment
    (folder / existing).write_text("human work", encoding="utf-8")
    with pytest.raises(FileExistsError):
        create_review(folder)
    assert (folder / existing).read_text() == "human work"
    other = "quality-review-key.json" if existing == "quality-review.json" else "quality-review.json"
    assert not (folder / other).exists()
    assert create_review(folder, "review-v2") == 2
    assert (folder / existing).read_text() == "human work"


@pytest.mark.parametrize("kind", ["source_hash", "question", "category", "variant", "scenario", "duplicate", "empty"])
def test_inconsistent_experiment_is_rejected_before_output(experiment, kind):
    folder, source, index = experiment
    if kind == "source_hash":
        source.write_text(source.read_text(encoding="utf-8") + " ", encoding="utf-8")
    elif kind in {"question", "category", "variant"}:
        path = folder / index["runs"][0]["file"]
        sample = json.loads(path.read_text(encoding="utf-8"))
        sample[kind] = "different"
        write_json(path, sample)
    elif kind == "scenario":
        index["runs"][0]["scenario"] = True
    elif kind == "duplicate":
        index["runs"].append(index["runs"][0])
    else:
        index["runs"] = []
    write_json(folder / "index.json", index)
    with pytest.raises(ValueError):
        create_review(folder)
    assert not (folder / "quality-review.json").exists()
    assert not (folder / "quality-review-key.json").exists()


def test_failed_execution_is_marked_without_a_human_verdict(experiment):
    folder, _, index = experiment
    path = folder / index["runs"][0]["file"]
    sample = json.loads(path.read_text(encoding="utf-8"))
    sample.update(status="failed", answer=None, llm_used=False)
    write_json(path, sample)
    create_review(folder)
    public = json.loads((folder / "quality-review.json").read_text(encoding="utf-8"))
    failed = next(case for case in public["cases"] if case["execution_status"] == "failed")
    assert failed["answer_origin"] == "unavailable" and failed["answer"] is None
    assert all(value is None for value in failed["scores"].values())


def test_missing_model_usage_never_claims_generated_or_fallback():
    assert answer_origin({"answer": {"answer": "부분 응답"}}) == "unknown"
    assert answer_origin({"answer": {"answer": "대체 안내"}, "llm_used": False}) == "fallback"


def test_output_prefix_cannot_select_another_directory(experiment):
    folder, _, _ = experiment
    with pytest.raises(ValueError):
        create_review(folder, "../other-review")


def test_git_line_ending_change_preserves_source_identity(experiment):
    folder, source, index = experiment
    original = source.read_bytes()
    changed = original.replace(b"\r\n", b"\n") if b"\r\n" in original else original.replace(b"\n", b"\r\n")
    assert changed != original
    source.write_bytes(changed)
    assert create_review(folder) == 2
    public = json.loads((folder / "quality-review.json").read_text(encoding="utf-8"))
    assert public["source_reference"]["sha256"] == index["input_sha256"]
    assert public["source_reference"]["normalized_lf_sha256"] == sha256(original.replace(b"\r\n", b"\n")).hexdigest()
