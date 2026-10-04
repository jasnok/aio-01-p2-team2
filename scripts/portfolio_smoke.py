"""Real API contract check with live SSE latency, followed by replay checks."""
import argparse
import json
import sys
import time
from pathlib import Path
from uuid import uuid4
from urllib.request import Request, urlopen
from urllib.error import HTTPError

SCENARIOS = [
    ("housing", "월세 계약이 종료되어 집을 인도했고 집주인에게 보증금 반환을 요청했지만 아직 받지 못했습니다. 관련 법령과 판례를 확인하고 싶습니다."),
    ("labor", "한 회사에서 주 40시간씩 2년 일하고 한 달 전에 퇴사했는데 퇴직금을 받지 못했습니다. 회사에 지급을 요청했지만 거절당했습니다. 관련 근거를 확인하고 싶습니다."),
    ("consumer", "온라인 쇼핑몰에서 운동화를 샀는데 배송된 상품에 하자가 있습니다. 수령 다음 날 사진과 함께 환불을 요청했지만 판매자가 거절했습니다. 관련 법령과 상담사례를 확인하고 싶습니다."),
    ("housing", "도와주세요. 어떻게 해야 할까요?"),
]


def request(base, path, headers, body=None):
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    with urlopen(Request(base + path, data=data, headers=headers), timeout=30) as response:
        return json.load(response)


def consume_sse(lines, started, clock=time.monotonic):
    events, current = [], {}
    first_evidence = terminal = None
    for raw in lines:
        line = raw.decode().strip() if isinstance(raw, bytes) else raw.strip()
        if line.startswith("id:"):
            current["id"] = int(line[3:].strip())
        elif line.startswith("event:"):
            current["event"] = line[6:].strip()
        elif line.startswith("data:"):
            current["data"] = json.loads(line[5:].strip())
        elif not line and "data" in current:
            elapsed = round((clock()-started)*1000)
            events.append(current)
            if current["data"].get("evidence_previews") and first_evidence is None:
                first_evidence = elapsed
            if current.get("event") in {"run.completed", "input.required", "run.failed"}:
                terminal = elapsed
            current = {}
    return {"events": events, "first_evidence_ms": first_evidence,
            "terminal_ms": terminal, "stream_completed": terminal is not None}


def citation_integrity(final):
    """Check nonempty claims and exact source quotes, without judging legal correctness."""
    def nonempty(value):
        return isinstance(value, str) and bool(value.strip())

    originals = {}
    for field in ("related_laws", "similar_cases", "consultations"):
        evidence = final.get(field, [])
        if not isinstance(evidence, list):
            return False
        for item in evidence:
            if not isinstance(item, dict):
                return False
            identifier, content = item.get("evidence_id"), item.get("content")
            if not nonempty(identifier) or not nonempty(content):
                return False
            if identifier in originals and originals[identifier] != content:
                return False
            originals[identifier] = content
    claims = final.get("cited_claims")
    if not isinstance(claims, list) or not claims:
        return False
    for claim in claims:
        if not isinstance(claim, dict) or not nonempty(claim.get("text")):
            return False
        citations = claim.get("citations")
        if not isinstance(citations, list) or not citations:
            return False
        for citation in citations:
            if not isinstance(citation, dict):
                return False
            identifier, quote = citation.get("evidence_id"), citation.get("quote")
            if not nonempty(identifier) or not nonempty(quote):
                return False
            if identifier not in originals or quote not in originals[identifier]:
                return False
    return True


def run_scenario(base, category, question, require_llm=False):
    started = time.monotonic()
    headers = {"Content-Type": "application/json", "X-Guest-Id": str(uuid4()), "Idempotency-Key": str(uuid4())}
    record = {"category": category, "question": question}
    try:
        created = request(base, "/api/agent-runs", headers, {"category": category, "question": question})
        path = "/api/agent-runs/" + created["run_id"]
        with urlopen(Request(base + path + "/events", headers=headers), timeout=180) as stream:
            live = consume_sse(stream, started)
        record["live_sse"] = {key: value for key, value in live.items() if key != "events"}
        record["elapsed_ms"] = live["terminal_ms"] or round((time.monotonic()-started)*1000)
        result = record["run"] = request(base, path, headers)
        duplicate = request(base, "/api/agent-runs", headers, {"category": category, "question": question})
        final = result.get("result") or {}
        checks = record["checks"] = {"idempotency": duplicate["run_id"] == created["run_id"],
            "real_mode": final.get("is_mock") is False, "live_sse_terminal": live["stream_completed"],
            "terminal_status": result["status"] in {"completed", "stopped"}}
        try:
            request(base, path, {"X-Guest-Id": str(uuid4())})
            checks["owner_isolation"] = False
        except HTTPError as error:
            checks["owner_isolation"] = error.code == 404
        with urlopen(Request(base + path + "/events", headers=headers), timeout=30) as stream:
            replay = consume_sse(stream, started)
        ids = [event["id"] for event in replay["events"]]
        checks["sse_replay"] = bool(ids) and ids == list(range(1, len(ids)+1))
        checks["live_sse_sequence"] = [event["id"] for event in live["events"]] == ids
        if final.get("generation_status") == "llm":
            checks["citation_integrity"] = citation_integrity(final)
            if final.get("diagnostics", {}).get("citation_mode") == "spans":
                checks["answer_matches_cited_claims"] = checks["citation_integrity"] and (
                    final.get("answer") == "\n\n".join(claim["text"] for claim in final["cited_claims"]))
        if final.get("diagnostics", {}).get("tool_timings_ms"):
            checks["early_evidence_events"] = final["diagnostics"].get("evidence_count", 0) == 0 or live["first_evidence_ms"] is not None
        if require_llm:
            checks["llm_generated"] = final.get("generation_status") == "llm"
    except Exception as error:
        record["error"] = type(error).__name__
    record.setdefault("elapsed_ms", round((time.monotonic()-started)*1000))
    record["check_duration_ms"] = round((time.monotonic()-started)*1000)-record["elapsed_ms"]
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--output", required=True)
    parser.add_argument("--require-llm", action="store_true")
    parser.add_argument("--cache-state", choices=["uncontrolled", "cold", "primed"], default="uncontrolled")
    parser.add_argument("--scenarios", nargs="+", type=int, choices=[0, 1, 2, 3], default=[0, 1, 2, 3])
    args = parser.parse_args()
    from benchmark_cache import cold_cache, prime_cache
    records = []
    for index, (category, question) in enumerate(SCENARIOS):
        if index not in args.scenarios:
            continue
        cache = {"method": "uncontrolled"}
        try:
            if args.cache_state == "cold":
                cache = cold_cache()
            elif args.cache_state == "primed" and index < 3:
                cache = prime_cache(args.base_url, category, question, request)
            record = run_scenario(args.base_url, category, question, args.require_llm and index < 3)
        except Exception as error:
            record = {"category": category, "question": question, "elapsed_ms": 0,
                      "error": "cache_control_failed", "error_type": type(error).__name__}
            cache = {"method": args.cache_state, "control_succeeded": False}
        record["cache_control"] = cache
        record["scenario_index"] = index
        records.append(record)
        destination = Path(args.output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        print(category, record.get("run", {}).get("status", record.get("error")), record["elapsed_ms"], flush=True)
    return int(any(item.get("error") or not item.get("checks") or not all(item["checks"].values()) for item in records))


if __name__ == "__main__":
    sys.exit(main())
