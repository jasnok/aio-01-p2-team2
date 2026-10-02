"""Create blind review forms from synthetic latency experiments; no invented scores."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re


def answer_origin(sample):
    if not sample.get("answer"):
        return "unavailable"
    if sample.get("llm_used") is True:
        return "generated"
    if sample.get("llm_used") is False:
        return "fallback"
    return "unknown"


def normalized_bytes(data):
    return data.replace(b"\r\n", b"\n")


def source_matches(data, recorded_digest):
    normalized = normalized_bytes(data)
    # Git may change LF/CRLF on checkout. Reconstruct only those exact byte
    # representations; all other source edits still fail the recorded hash.
    return any(sha256(value).hexdigest() == recorded_digest for value in
               (data, normalized, normalized.replace(b"\n", b"\r\n")))


def review_evidence(case):
    final = case["run"]["result"]
    evidence = []
    for field in ("related_laws", "similar_cases", "consultations"):
        for item in final[field]:
            if not isinstance(item, dict) or any(not isinstance(item.get(key), str) for key in ("evidence_id", "title", "content")):
                raise ValueError("원문 근거 ID·제목·내용 문자열이 필요합니다.")
            source = item.get("source") or {}
            if not isinstance(source, dict):
                raise ValueError("근거 출처는 객체여야 합니다.")
            evidence.append({key: item[key] for key in ("evidence_id", "title", "content")})
            evidence[-1]["source"] = {key: source[key] for key in ("title", "source_type", "url") if key in source}
    return evidence


def create_review(folder, output_prefix="quality-review"):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", output_prefix):
        raise ValueError("출력 이름에는 영문·숫자·밑줄·하이픈만 사용할 수 있습니다.")
    outputs = [folder / f"{output_prefix}.json", folder / f"{output_prefix}-key.json"]
    if any(path.exists() for path in outputs):
        raise FileExistsError("기존 검토 자료를 보존합니다. 다른 --output-prefix를 지정하세요.")
    index = json.loads((folder/"index.json").read_text(encoding="utf-8"))
    source_bytes = Path(index["input"]).read_bytes()
    if not source_matches(source_bytes, index["input_sha256"]):
        raise ValueError("비교 실험의 원본 SHA-256이 다릅니다.")
    source = json.loads(source_bytes)
    if not isinstance(source, list) or not isinstance(index.get("runs"), list) or not index["runs"]:
        raise ValueError("원본 시나리오 목록과 비교 실행 목록이 필요합니다.")
    rows, private = [], []
    seen = set()
    for row in index["runs"]:
        filename, scenario = row["file"], row["scenario"]
        if not isinstance(filename, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+\.json", filename) or filename in seen:
            raise ValueError("실행 파일 이름이 잘못되었거나 중복되었습니다.")
        seen.add(filename)
        if type(scenario) is not int or not 0 <= scenario < len(source):
            raise ValueError("실행의 원본 시나리오 번호가 잘못되었습니다.")
        sample_bytes = (folder / filename).read_bytes()
        sample = json.loads(sample_bytes)
        case = source[scenario]
        if sample["question"] != case["question"] or sample["category"] != case["category"] or sample["variant"] != row["variant"]:
            raise ValueError("실행 질문·범주·설정이 비교 기록과 다릅니다.")
        if sample.get("status") not in {"completed", "failed"}:
            raise ValueError("실행 성공/실패 상태가 필요합니다.")
        identifier = sha256(row["file"].encode()).hexdigest()[:12]
        rows.append({"review_id": identifier, "question": sample["question"],
            "scope": sample.get("scope", "pipeline"), "intake": sample.get("intake"),
            "execution_status": sample["status"],
            "answer_origin": answer_origin(sample),
            "evidence": review_evidence(case),
            "answer": sample.get("answer"), "reviewer": None, "scores": {
                "input_decision_correct": None, "question_answered": None,
                "all_claims_supported": None, "conditions_and_exceptions_preserved": None,
                "abstention_appropriate": None}, "notes": None})
        private.append({"review_id": identifier, "file": filename, "variant": row["variant"],
                        "sample_sha256_lf": sha256(normalized_bytes(sample_bytes)).hexdigest()})
    rows.sort(key=lambda row: row["review_id"])
    public = {"schema_version": 2, "status": "pending_human_review",
        "evidence_scope": "fixed candidate evidence; selected model context may be a subset",
        "source_reference": {"file": index["input"], "sha256": index["input_sha256"],
                             "normalized_lf_sha256": sha256(normalized_bytes(source_bytes)).hexdigest()},
        "scoring": "true/false with justification; compare each claim with exact source quotes; do not use model verdict as label",
        "cases": rows}
    for path, payload in zip(outputs, (public, private)):
        with path.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
    return len(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path)
    parser.add_argument("--output-prefix", default="quality-review")
    args = parser.parse_args()
    print(create_review(args.folder, args.output_prefix))


if __name__ == "__main__":
    main()
