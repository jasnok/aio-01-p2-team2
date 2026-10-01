"""Small real-server check. Calls the configured LLM; never saves permanent history."""

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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--output", required=True)
    parser.add_argument("--require-llm", action="store_true")
    args = parser.parse_args()
    records = []
    for category, question in SCENARIOS:
        started = time.monotonic()
        headers = {"Content-Type": "application/json", "X-Guest-Id": str(uuid4()), "Idempotency-Key": str(uuid4())}
        record = {"category": category, "question": question, "guest_id": headers["X-Guest-Id"]}
        try:
            created = request(args.base_url, "/api/agent-runs", headers, {"category": category, "question": question})
            path = "/api/agent-runs/" + created["run_id"]
            while time.monotonic() - started < 180:
                result = request(args.base_url, path, headers)
                if result["status"] in {"completed", "stopped", "failed"}:
                    record["run"] = result
                    duplicate = request(args.base_url, "/api/agent-runs", headers, {"category": category, "question": question})
                    record["checks"] = {"idempotency": duplicate["run_id"] == created["run_id"],
                                        "real_mode": result.get("result", {}).get("is_mock") is False}
                    try:
                        request(args.base_url, path, {"X-Guest-Id": str(uuid4())})
                        record["checks"]["owner_isolation"] = False
                    except HTTPError as error:
                        record["checks"]["owner_isolation"] = error.code == 404
                    with urlopen(Request(args.base_url + path + "/events", headers=headers), timeout=30) as events:
                        replay = events.read().decode()
                    ids = [int(line[4:]) for line in replay.splitlines() if line.startswith("id: ")]
                    record["checks"]["sse_replay"] = bool(ids) and ids == list(range(1, len(ids) + 1))
                    if args.require_llm and len(records) < 3:
                        record["checks"]["llm_generated"] = result.get("result", {}).get("generation_status") == "llm"
                    break
                time.sleep(0.5)
            else:
                record["error"] = "poll_timeout"
        except Exception as error:
            record["error"] = type(error).__name__
        record["elapsed_ms"] = round((time.monotonic() - started) * 1000)
        records.append(record)
        destination = Path(args.output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        print(category, record.get("run", {}).get("status", record.get("error")), record["elapsed_ms"], flush=True)
    return int(any(item.get("error") or item.get("run", {}).get("status") == "failed"
                   or not all(item.get("checks", {}).values()) for item in records))


if __name__ == "__main__":
    sys.exit(main())
