"""Bounded SSE receiver. Reconnects an existing run, never creates a second run."""

import json
import time
from urllib.parse import quote

import httpx
from pydantic import ValidationError

from frontend.clients import backend_client as api
from frontend.core.config import get_frontend_settings
from frontend.core.models import LegalQuestionView

EVENTS = {"run.started", "step.started", "step.completed", "input.required", "run.completed", "run.failed"}
TERMINAL = {"completed", "stopped", "failed"}


def parse_sse(lines):
    event, event_id, data = "message", None, []
    for line in lines:
        if not line:
            if data:
                yield event_id, event, json.loads("\n".join(data))
            event, event_id, data = "message", None, []
        elif not line.startswith(":"):
            field, _, value = line.partition(":")
            value = value.removeprefix(" ")
            if field == "event":
                event = value
            elif field == "id":
                event_id = value
            elif field == "data":
                data.append(value)


def final_result(snapshot, run_id):
    if snapshot.get("run_id") != run_id:
        raise api.BackendClientError("작업 ID가 일치하지 않습니다.", "CONTRACT_MISMATCH")
    status = snapshot.get("status")
    if status == "failed":
        raise api.BackendClientError("분석 작업이 실패했습니다. 작업 ID로 서버 로그를 확인해 주세요.", "RUN_FAILED")
    if status in {"completed", "stopped"}:
        try:
            result = LegalQuestionView.model_validate(snapshot["result"])
            if result.is_mock or result.status != status:
                raise ValueError("Invalid final status")
            return result.model_dump(mode="json")
        except (KeyError, ValueError, ValidationError) as error:
            raise api.BackendClientError("최종 분석 결과가 계약과 다릅니다.", "CONTRACT_MISMATCH") from error
    if status not in {"queued", "running"}:
        raise api.BackendClientError("알 수 없는 작업 상태입니다.", "CONTRACT_MISMATCH")
    return None


def receive_run(token, guest_id, run_id, last_id=0, on_event=lambda *args: None):
    settings = get_frontend_settings()
    deadline = time.monotonic() + settings.frontend_sse_total_timeout_seconds
    headers = {**api.auth_headers(token, guest_id), "Accept": "text/event-stream"}
    url = f"{settings.normalized_backend_url}/api/agent-runs/{quote(run_id, safe='')}/events"
    # Initial connection plus two reconnects. Snapshots recover missed terminal events.
    for attempt in range(3):
        result = final_result(api.get_agent_run(token, guest_id, run_id), run_id)
        if result is not None:
            return result
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        headers["Last-Event-ID"] = str(last_id)
        try:
            with httpx.stream("GET", url, headers=headers,
                              timeout=httpx.Timeout(min(30, remaining), connect=min(5, remaining))) as response:
                response.raise_for_status()
                if "text/event-stream" not in response.headers.get("content-type", ""):
                    raise api.BackendClientError("SSE 서버가 아직 준비되지 않았습니다.", "CONTRACT_MISMATCH")
                response.encoding = "utf-8"
                def bounded_lines():
                    for line in response.iter_lines():
                        if time.monotonic() >= deadline:
                            raise TimeoutError("전체 분석 대기시간 초과")
                        yield line
                for event_id, event, data in parse_sse(bounded_lines()):
                    if event not in EVENTS or not isinstance(data, dict) or data.get("run_id") != run_id:
                        raise ValueError("Invalid SSE event")
                    number = int(event_id)
                    if number <= last_id:
                        continue
                    if event.startswith("step.") and not data.get("step_id"):
                        raise ValueError("Missing step_id")
                    on_event(number, event, data)
                    last_id = number
                    if event in {"run.completed", "input.required", "run.failed"}:
                        result = final_result(api.get_agent_run(token, guest_id, run_id), run_id)
                        if result is None:
                            raise ValueError("Terminal event before persisted result")
                        return result
        except httpx.HTTPStatusError as error:
            code, message = api._extract_api_error(error.response)
            raise api.BackendClientError(message, code) from error
        except (httpx.TransportError, TimeoutError):
            pass
        except (ValueError, TypeError) as error:
            raise api.BackendClientError("진행 이벤트 형식이 계약과 다릅니다.", "CONTRACT_MISMATCH") from error
    result = final_result(api.get_agent_run(token, guest_id, run_id), run_id)
    if result is not None:
        return result
    raise api.BackendClientError("진행 연결이 끊겼습니다. 같은 질문으로 다시 시도하면 기존 작업을 조회합니다.", "SSE_DISCONNECTED")
