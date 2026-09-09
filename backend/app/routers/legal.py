from datetime import timedelta
import logging
import time
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from backend.app.agents.models import AgentState
from backend.app.agents.registry import get_agent_profile
from backend.app.agents.runtime import LegalAgentRuntime
from backend.app.schemas.legal import (
    Category,
    Evidence,
    LegalQuestionRequest,
    LegalQuestionResponse,
    LegalSearchResponse,
)
from backend.app.services.legal_question_service import answer_question, answer_question_from_mcp
from backend.app.services.conversation_service import ConversationService
from backend.app.services.mock_store import iso, now, store
from backend.app.core.config import get_settings
from backend.app.routers.mock_api import actor


router = APIRouter(prefix="/api/legal", tags=["legal"])
logger = logging.getLogger(__name__)
conversation_service = ConversationService()


@router.post("/questions", response_model=LegalQuestionResponse, summary="생활 법률 사례 분석", description="질문을 분야별로 분석합니다. Mock 모드에서는 실제 법률 판단 대신 연결 확인용 안내를 돌려줍니다. 중복 클릭 방지를 위해 Idempotency-Key Header 사용을 권장합니다.")
async def create_question(request: LegalQuestionRequest, idempotency_key: str | None = Header(default=None), x_guest_id: str | None = Header(default=None), x_mock_scenario: str | None = Header(default=None), value: dict = Depends(actor)) -> LegalQuestionResponse:
    # session_id는 기존 계약 호환용이고, 저장 대화의 소유자는 검증된 actor를 사용한다.
    owner = value["id"]
    if idempotency_key:
        cached = store.idempotency.get((owner, "/api/legal/questions", idempotency_key))
        if cached and cached[0] > now():
            return LegalQuestionResponse.model_validate(cached[1])

    if request.conversation_id is not None:
        context = await conversation_service.build_context_for_actor(
            conversation_id=request.conversation_id,
            actor_key=owner,
        )
        if not context:
            raise HTTPException(
                status_code=404,
                detail={"code": "CONVERSATION_NOT_FOUND", "message": "저장된 대화를 찾을 수 없습니다."},
            )
    if x_mock_scenario and not get_settings().backend_mock_mode:
        raise HTTPException(status_code=400, detail={"code": "INVALID_REQUEST", "message": "운영 모드에서는 Mock 시나리오를 사용할 수 없습니다."})
    if x_mock_scenario in {"mcp_error", "database_error", "timeout", "invalid_response"}:
        mapping = {"mcp_error": (502, "MCP_UNAVAILABLE"), "database_error": (503, "DATABASE_UNAVAILABLE"), "timeout": (504, "UPSTREAM_TIMEOUT"), "invalid_response": (502, "MCP_UNAVAILABLE")}
        status, code = mapping[x_mock_scenario]
        raise HTTPException(status_code=status, detail={"code": code, "message": "Mock 장애 시나리오가 실행되었습니다."})
    if x_mock_scenario == "no_results":
        response = LegalQuestionResponse(request_id=f"req-{owner}", agent_id=request.category, termination_reason="no_results", question_summary="검색 결과가 없습니다.", answer="공식 검색 결과를 찾지 못했습니다.", cautions=["검색어와 사실관계를 보완해 다시 시도해 주세요."], is_mock=True)
    elif x_mock_scenario == "no_evidence":
        response = LegalQuestionResponse(request_id=f"req-{owner}", agent_id=request.category, termination_reason="no_evidence", question_summary="근거가 부족합니다.", answer="공식 근거가 충분하지 않아 답변을 만들지 않았습니다.", cautions=["공식 기관 자료를 추가 확인해 주세요."], is_mock=True)
    else:
        if not get_settings().backend_mock_mode:
            try:
                if request.conversation_id is None:
                    response = await answer_question_from_mcp(request)
                else:
                    response = await answer_question_from_mcp(
                        request,
                        conversation_context=context,
                    )
            except TimeoutError as error:
                raise HTTPException(status_code=504, detail={"code": "UPSTREAM_TIMEOUT", "message": "Legal MCP 응답 시간이 초과되었습니다."}) from error
            except Exception as error:
                raise HTTPException(status_code=502, detail={"code": "MCP_UNAVAILABLE", "message": "Legal MCP 검색 서비스에 연결할 수 없습니다."}) from error
        else:
            response = answer_question(request)
    if request.save_selected:
        try:
            saved = await conversation_service.save_if_selected(
                save_selected=True,
                actor_key=owner,
                question=request.question,
                response=response,
                conversation_id=request.conversation_id,
            )
            response.conversation_id = saved["conversation_id"] if saved else None
        except Exception as error:
            logger.exception(
                "conversation_save_failed request_id=%s reason=%s",
                response.request_id,
                type(error).__name__,
            )
            raise HTTPException(
                status_code=503,
                detail={"code": "CONVERSATION_SAVE_FAILED", "message": "대화 저장에 실패했습니다. 분석 결과는 저장되지 않았습니다."},
            ) from error
    if idempotency_key:
        store.idempotency[(owner, "/api/legal/questions", idempotency_key)] = (now() + timedelta(hours=24), response.model_dump(mode="json"))
    store.history.setdefault(owner, []).append({"id": f"history-{response.request_id}", "type": "legal_analysis", "target_id": response.request_id, "category": request.category, "title": request.question[:100], "created_at": iso()})
    store.notify(owner, "ANALYSIS_COMPLETED" if response.termination_reason == "model_finished" else "ANALYSIS_NO_RESULTS", "사례 분석 완료", "사례 분석 결과를 확인해 주세요.", target_type="legal_analysis", target_id=response.request_id, category=request.category)
    return response


async def _search_by_tool(
    *,
    category: Category,
    query: str,
    top_k: int,
    tool_name: str,
    expected_source_type: str,
) -> LegalSearchResponse:
    request_id = f"req-{uuid4()}"
    normalized_query = query.strip()
    if not 2 <= len(normalized_query) <= 200:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "query는 공백을 제외하고 2~200자여야 합니다."},
        )

    started_at = time.perf_counter()
    try:
        profile = get_agent_profile(category)
        state, raw_items = await LegalAgentRuntime().run_single_tool(
            profile,
            AgentState(request_id=request_id, agent_id=profile.agent_id, question=normalized_query),
            tool_name,
            top_k,
        )
        items = [Evidence.model_validate(item) for item in raw_items]
        if any(item.source.source_type != expected_source_type for item in items):
            raise ValueError("MCP가 요청한 자료 유형과 다른 결과를 반환했습니다.")
        logger.info(
            "legal_search request_id=%s tool=%s category=%s result_count=%s duration_ms=%s",
            request_id,
            tool_name,
            category,
            len(items),
            round((time.perf_counter() - started_at) * 1000),
        )
        return LegalSearchResponse(
            request_id=request_id,
            query=normalized_query,
            category=category,
            items=items,
            total=len(items),
            is_mock=get_settings().backend_mock_mode,
        )
    except TimeoutError as error:
        logger.warning("legal_search_failed request_id=%s tool=%s category=%s reason=timeout", request_id, tool_name, category)
        raise HTTPException(status_code=504, detail={"code": "UPSTREAM_TIMEOUT", "message": "Legal MCP 응답 시간이 초과되었습니다."}) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("legal_search_failed request_id=%s tool=%s category=%s reason=%s", request_id, tool_name, category, type(error).__name__)
        raise HTTPException(status_code=502, detail={"code": "MCP_UNAVAILABLE", "message": "Legal MCP 검색 서비스에 연결할 수 없습니다."}) from error


@router.get("/laws", response_model=LegalSearchResponse, summary="법령 검색", description="Agent가 법령 검색 Tool만 실행합니다. 결과가 없으면 빈 배열을 반환합니다.")
async def search_laws(category: Category, query: str, top_k: int = Query(3, ge=1, le=10)) -> LegalSearchResponse:
    return await _search_by_tool(category=category, query=query, top_k=top_k, tool_name="search_laws", expected_source_type="law")


@router.get("/cases", response_model=LegalSearchResponse, summary="판례 검색", description="Agent가 판례 검색 Tool만 실행합니다. 결과가 없으면 빈 배열을 반환합니다.")
async def search_cases(category: Category, query: str, top_k: int = Query(3, ge=1, le=10)) -> LegalSearchResponse:
    return await _search_by_tool(category=category, query=query, top_k=top_k, tool_name="search_cases", expected_source_type="case")


@router.get("/consultations", response_model=LegalSearchResponse, summary="상담사례 검색", description="Agent가 상담사례 검색 Tool만 실행합니다. 결과가 없으면 빈 배열을 반환합니다.")
async def search_consultations(category: Category, query: str, top_k: int = Query(3, ge=1, le=10)) -> LegalSearchResponse:
    return await _search_by_tool(category=category, query=query, top_k=top_k, tool_name="search_consultations", expected_source_type="consultation")


@router.get("/terms", summary="쉬운 법률 용어 검색", description="어려운 법률 용어를 쉬운 말로 설명합니다.")
def search_terms(category: str, query: str = Query(min_length=2, max_length=200)) -> dict:
    terms = {"labor": {"임금체불": "정해진 때에 임금이 지급되지 않은 상태입니다."}, "housing": {"보증금": "임대차 계약에서 반환 조건을 정하는 금액입니다."}, "consumer": {"청약철회": "일정한 거래에서 계약을 취소할 수 있는 권리입니다."}}
    matched = [{"term": term, "description": description} for term, description in terms.get(category, {}).items() if query.strip() in term or query.strip() in description]
    return {"items": matched}

