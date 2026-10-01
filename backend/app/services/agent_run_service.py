"""실제 분석 작업의 상태와 SSE 이벤트를 관리한다.

실제 모드는 Redis에 상태와 이벤트를 보관하며 Mock 모드는 메모리를 사용한다.
실행 작업 자체는 API 프로세스의 asyncio task이며 자동 재개 작업 큐는 아니다.
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
from backend.app.services.agent_run_store import (
    SnapshotConflictError, save_snapshot, enabled as persistent_runs_enabled,
)
from backend.app.services.run_metrics import log_result
from backend.app.services.actor_identity import actor_key
from backend.app.services.run_capacity import RunSlot, run_capacity


logger = logging.getLogger(__name__)
_active_tasks: set[asyncio.Task] = set()


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
    cache_enabled: bool = True,
) -> tuple[dict, bool]:
    normalized_question = question.strip()
    key = (actor_key(owner), idempotency_key)
    cached = store.agent_run_idempotency.get(key)
    fingerprint = (category, normalized_question, save_selected, conversation_id)
    if cache_enabled and cached and cached["expires_at"] > now():
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
        "revision": 0,
        "result": None,
        "error": None,
        "events": [],
        "created_at": iso(),
        "updated_at": iso(),
    }
    store.agent_runs[run_id] = run
    if cache_enabled:
        store.agent_run_idempotency[key] = {
            "run_id": run_id,
            "fingerprint": fingerprint,
            "expires_at": now() + timedelta(hours=24),
        }
    return run, True


async def _execute_run(run_id: str) -> None:
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
    await save_snapshot(run)
    failure_stage = "context"
    step_ids: dict[str, list[str]] = {}
    validation_step_id: str | None = None
    generation_step_id: str | None = None
    tool_messages = {
        "search_laws": "관련 법령을 검색하고 있습니다.",
        "search_cases": "유사 판례를 검색하고 있습니다.",
        "search_consultations": "상담사례를 검색하고 있습니다.",
        "search_legal_documents": "관련 법률 자료를 검색하고 있습니다.",
    }

    async def on_runtime_event(trace: dict) -> None:
        nonlocal validation_step_id, generation_step_id, failure_stage
        tool = trace.get("tool")
        stage = trace.get("stage")
        if stage in {"validation_started", "tool_selected", "generation_started"}:
            failure_stage = {"validation_started": "validation", "tool_selected": "retrieval", "generation_started": "generation"}[stage]
        if stage == "validation_started":
            validation_step_id = f"validation-{uuid4()}"
            append_event(run, "step.started", {
                "run_id": run_id, "step_id": validation_step_id, "stage": "validation",
                "status": "started", "tool": None,
                "message": "질문 내용을 확인하고 있습니다.", "result_count": None,
            })
        elif stage == "generation_started":
            generation_step_id = f"generation-{uuid4()}"
            append_event(run, "step.started", {
                "run_id": run_id, "step_id": generation_step_id, "stage": "generation",
                "status": "started", "tool": None, "message": "검색 근거로 답변을 작성하고 인용을 확인하고 있습니다.",
                "result_count": None,
            })
        elif stage == "generation_completed":
            append_event(run, "step.completed", {
                "run_id": run_id, "step_id": generation_step_id, "stage": "generation",
                "status": "completed", "tool": None,
                "message": "답변과 인용 확인을 마쳤습니다." if trace.get("llm_used") else "검색 자료 안내를 준비했습니다.",
                "result_count": None,
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
            previews = [{"evidence_id": item.get("evidence_id"), "title": item.get("title", ""),
                         "content_preview": str(item.get("content", ""))[:180],
                         "source_type": (item.get("source") or {}).get("source_type", "external")}
                        for item in trace.get("evidence", [])[:3]]
            append_event(run, "step.completed", {
                "run_id": run_id, "step_id": step_id, "stage": "retrieval",
                "status": "completed", "tool": tool,
                "message": "관련 자료 검색을 완료했습니다.",
                "result_count": trace.get("result_count"),
                "evidence_previews": previews,
            })
        await save_snapshot(run)

    conflicted = False
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
        failure_stage = "analysis"
        if context is None:
            result = await answer_question_from_mcp(request, event_callback=on_runtime_event)
        else:
            result = await answer_question_from_mcp(
                request,
                event_callback=on_runtime_event,
                conversation_context=context,
            )
        failure_stage = "storage"
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
                    execution_key=run_id,
                )
        # 반드시 결과를 먼저 저장한 뒤 terminal 이벤트를 발행한다.
        run["result"] = result.model_dump(mode="json")
        log_result(run_id, result)
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
    except SnapshotConflictError:
        conflicted = True
        raise
    except Exception as error:
        logger.error("agent_run_failed run_id=%s stage=%s error_type=%s", run_id, failure_stage, type(error).__name__)
        # 내부 예외와 민감한 연결 정보는 SSE/HTTP 응답에 노출하지 않는다.
        run["status"] = "failed"
        run["error"] = {"code": "ANALYSIS_FAILED", "message": "법률 분석 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."}
        append_event(run, "run.failed", {
            "run_id": run_id, "status": "failed", "message": run["error"]["message"],
        })
    finally:
        if not conflicted:
            try:
                await save_snapshot(run)
            except SnapshotConflictError:
                raise
            except Exception:
                logger.error("agent_run_snapshot_failed run_id=%s", run_id)


def _adopt_snapshot(run_id: str, conflict: SnapshotConflictError) -> None:
    """Discard local writes after losing ownership of the snapshot revision."""
    logger.warning("agent_run_snapshot_conflict run_id=%s reason=%s", run_id, conflict.reason)
    run = store.agent_runs.pop(run_id, None)
    if run is not None and conflict.current is not None:
        run.clear()
        run.update(conflict.current)


async def execute_run(run_id: str) -> None:
    try:
        async with asyncio.timeout(get_settings().agent_run_timeout_seconds):
            await _execute_run(run_id)
    except SnapshotConflictError as conflict:
        _adopt_snapshot(run_id, conflict)
    except Exception as error:
        run = store.agent_runs.get(run_id)
        if run is None:
            return
        if run["status"] not in TERMINAL_STATUSES:
            run["status"] = "failed"
            run["error"] = {"code": "ANALYSIS_TIMEOUT" if isinstance(error, TimeoutError) else "RUN_STORE_UNAVAILABLE",
                            "message": "분석을 완료하지 못했습니다. 잠시 후 다시 시도해 주세요."}
            append_event(run, "run.failed", {"run_id": run_id, "status": "failed", "message": run["error"]["message"]})
        try:
            await save_snapshot(run)
        except SnapshotConflictError as conflict:
            _adopt_snapshot(run_id, conflict)
        except Exception:
            logger.error("agent_run_snapshot_failed run_id=%s", run_id)
    finally:
        run = store.agent_runs.get(run_id)
        if persistent_runs_enabled() and run and run["status"] in TERMINAL_STATUSES:
            store.agent_runs.pop(run_id, None)


def start_run(run_id: str, slot: RunSlot | None = None) -> asyncio.Task[None]:
    slot = slot or run_capacity.acquire()
    try:
        task = asyncio.create_task(execute_run(run_id))
    except BaseException:
        slot.release()
        raise
    _active_tasks.add(task)
    task.add_done_callback(_active_tasks.discard)
    task.add_done_callback(lambda _: slot.release())
    return task


async def close_active_runs() -> None:
    tasks = list(_active_tasks)
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
