"""실제 분석 작업의 상태와 SSE 이벤트를 관리한다.

현재 MVP는 단일 프로세스 메모리를 사용한다. Redis를 붙일 때 이 모듈의
저장 부분만 교체하면 HTTP/SSE 계약은 유지된다.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import timedelta
from time import monotonic
from uuid import uuid4

from backend.app.schemas.legal import Category, LegalQuestionRequest
from backend.app.services.legal_question_service import answer_question_from_mcp
from backend.app.services.conversation_service import ConversationService
from backend.app.services.saved_conversation_service import SavedConversationService
from backend.app.services.guest_session_service import guest_sessions
from backend.app.core.config import get_settings
from backend.app.services.mock_store import iso, now, store


logger = logging.getLogger(__name__)


TERMINAL_STATUSES = {"completed", "stopped", "failed"}
conversation_service = ConversationService()
saved_conversation_service = SavedConversationService()


def append_event(run: dict, event: str, data: dict) -> None:
    """작업별 증가 번호를 붙여 재연결 때 같은 이벤트를 다시 보낼 수 있게 한다."""
    run["events"].append({"id": len(run["events"]) + 1, "event": event, "data": data})
    run["updated_at"] = iso()


def public_run(run: dict) -> dict:
    result = {
        "run_id": run["run_id"],
        "status": run["status"],
        "result": run.get("result"),
    }
    if run.get("error"):
        result["error"] = run["error"]
    return result


def create_run(
    owner: dict,
    category: Category,
    question: str,
    idempotency_key: str,
    *,
    save_selected: bool = False,
    conversation_id: int | None = None,
) -> tuple[dict, bool]:
    normalized_question = question.strip()
    key = (owner["id"], idempotency_key)
    cached = store.agent_run_idempotency.get(key)
    fingerprint = (category, normalized_question, save_selected, conversation_id)
    if cached and cached["expires_at"] > now():
        if cached["fingerprint"] != fingerprint:
            raise ValueError("IDEMPOTENCY_CONFLICT")
        return store.agent_runs[cached["run_id"]], False

    run_id = f"run-{uuid4()}"
    run = {
        "run_id": run_id,
        "owner_id": owner["id"],
        "actor": {"id": owner["id"], "role": owner["role"]},
        "category": category,
        "question": normalized_question,
        "save_selected": save_selected,
        "conversation_id": conversation_id,
        "status": "queued",
        "result": None,
        "error": None,
        "events": [],
        "created_at": iso(),
        "updated_at": iso(),
    }
    store.agent_runs[run_id] = run
    store.agent_run_idempotency[key] = {
        "run_id": run_id,
        "fingerprint": fingerprint,
        "expires_at": now() + timedelta(hours=24),
    }
    return run, True


async def execute_run(run_id: str) -> None:
    """MCP 완료를 기다리되, HTTP 생성 요청은 기다리지 않는 실제 작업 본문이다."""
    run = store.agent_runs.get(run_id)
    if not run or run["status"] != "queued":
        return

    run["status"] = "running"
    append_event(run, "run.started", {
        "run_id": run_id,
        "status": "running",
        "message": "법률 분석을 시작했습니다.",
    })
    step_ids: dict[str, list[str]] = {}
    validation_step_id: str | None = None
    tool_messages = {
        "search_laws": "관련 법령을 검색하고 있습니다.",
        "search_cases": "유사 판례를 검색하고 있습니다.",
        "search_consultations": "상담사례를 검색하고 있습니다.",
        "search_legal_documents": "관련 법률 자료를 검색하고 있습니다.",
    }

    async def on_runtime_event(trace: dict) -> None:
        nonlocal validation_step_id
        tool = trace.get("tool")
        stage = trace.get("stage")
        if stage == "validation_started":
            validation_step_id = f"validation-{uuid4()}"
            append_event(run, "step.started", {
                "run_id": run_id, "step_id": validation_step_id, "stage": "validation",
                "status": "started", "tool": None,
                "message": "질문 내용을 확인하고 있습니다.", "result_count": None,
            })
        elif stage == "validation_completed":
            append_event(run, "step.completed", {
                "run_id": run_id,
                "step_id": validation_step_id or f"validation-{uuid4()}",
                "stage": "validation", "status": "completed", "tool": None,
                "message": "질문 내용을 확인했습니다.", "result_count": None,
            })
        elif stage == "tool_selected":
            step_id = f"{tool}-{uuid4()}"
            step_ids.setdefault(str(tool), []).append(step_id)
            append_event(run, "step.started", {
                "run_id": run_id, "step_id": step_id, "stage": "retrieval",
                "status": "started", "tool": tool,
                "message": tool_messages.get(str(tool), "관련 법률 자료를 검색하고 있습니다."),
                "result_count": None,
            })
        elif stage == "tool_completed":
            step_id = step_ids.get(str(tool), [f"{tool}-unknown"]).pop(0)
            append_event(run, "step.completed", {
                "run_id": run_id, "step_id": step_id, "stage": "retrieval",
                "status": "completed", "tool": tool,
                "message": "관련 자료 검색을 완료했습니다.",
                "result_count": trace.get("result_count"),
            })

    try:
        context: list[dict] | None = None
        if run["conversation_id"] is not None:
            context = (
                await conversation_service.build_context_for_actor(
                    conversation_id=run["conversation_id"],
                    actor_key=run["owner_id"],
                )
                if get_settings().backend_mock_mode
                else await saved_conversation_service.build_context_for_actor(
                    actor=run["actor"],
                    conversation_id=run["conversation_id"],
                )
            )
            if not context:
                raise PermissionError("conversation is not owned by actor")
        request = LegalQuestionRequest(
            session_id=str(run["owner_id"]), category=run["category"], question=run["question"],
        )
        if context is None:
            result = await answer_question_from_mcp(request, event_callback=on_runtime_event)
        else:
            result = await answer_question_from_mcp(
                request,
                event_callback=on_runtime_event,
                conversation_context=context,
            )
        if run["save_selected"]:
            if get_settings().backend_mock_mode:
                saved = await conversation_service.save_if_selected(
                    save_selected=True,
                    actor_key=run["owner_id"],
                    question=run["question"],
                    response=result,
                    conversation_id=run["conversation_id"],
                )
                result.conversation_id = saved["conversation_id"] if saved else None
            elif run["actor"]["role"] != "GUEST":
                result.conversation_id = await saved_conversation_service.save_response(
                    actor=run["actor"],
                    category=run["category"],
                    question=run["question"],
                    response=result,
                )
        # 반드시 결과를 먼저 저장한 뒤 terminal 이벤트를 발행한다.
        run["result"] = result.model_dump(mode="json")
        if result.termination_reason == "needs_clarification":
            run["status"] = "stopped"
            if run["actor"]["role"] == "GUEST":
                try:
                    await guest_sessions.save_analysis(str(run["owner_id"]), run)
                except Exception:
                    logger.warning("guest_temporary_save_failed run_id=%s", run_id)
                    append_event(run, "guest.storage_failed", {
                        "run_id": run_id,
                        "message": "임시 이력을 저장하지 못했습니다. 분석 결과는 현재 화면에서 확인할 수 있습니다.",
                    })
            append_event(run, "input.required", {
                "run_id": run_id, "status": "stopped",
                "message": "정확한 분석을 위해 추가 정보가 필요합니다.",
            })
        else:
            run["status"] = "completed"
            if run["actor"]["role"] == "GUEST":
                try:
                    await guest_sessions.save_analysis(str(run["owner_id"]), run)
                except Exception:
                    logger.warning("guest_temporary_save_failed run_id=%s", run_id)
                    append_event(run, "guest.storage_failed", {
                        "run_id": run_id,
                        "message": "임시 이력을 저장하지 못했습니다. 분석 결과는 현재 화면에서 확인할 수 있습니다.",
                    })
            append_event(run, "run.completed", {
                "run_id": run_id, "status": "completed",
                "message": "법률 분석이 완료되었습니다.",
            })
    except Exception:
        logger.exception("agent_run_failed run_id=%s", run_id)
        # 내부 예외와 민감한 연결 정보는 SSE/HTTP 응답에 노출하지 않는다.
        run["status"] = "failed"
        run["error"] = {"code": "ANALYSIS_FAILED", "message": "법률 분석 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."}
        append_event(run, "run.failed", {
            "run_id": run_id, "status": "failed", "message": run["error"]["message"],
        })


def start_run(run_id: str) -> asyncio.Task[None]:
    return asyncio.create_task(execute_run(run_id))
