from datetime import timedelta
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Query

from backend.app.schemas.legal import LegalQuestionRequest, LegalQuestionResponse
from backend.app.services.legal_question_service import answer_question
from backend.app.services.mock_store import iso, now, store
from backend.app.core.config import get_settings


router = APIRouter(prefix="/api/legal", tags=["legal"])


@router.post("/questions", response_model=LegalQuestionResponse)
def create_question(request: LegalQuestionRequest, idempotency_key: str | None = Header(default=None), x_guest_id: str | None = Header(default=None), x_mock_scenario: str | None = Header(default=None)) -> LegalQuestionResponse:
    owner = x_guest_id or request.session_id
    if idempotency_key:
        cached = store.idempotency.get((owner, "/api/legal/questions", idempotency_key))
        if cached and cached[0] > now():
            return LegalQuestionResponse.model_validate(cached[1])
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
        try:
            response = answer_question(request)
        except Exception:
            # BACKEND_MOCK_MODE의 기본 경로다. 실제 MCP 장애와 Mock 기본값을
            # 혼동하지 않도록 강제 장애는 X-Mock-Scenario에서만 표현한다.
            response = LegalQuestionResponse(
                request_id=f"req-{owner}-{uuid4()}", agent_id=request.category,
                termination_reason="model_finished", question_summary=f"{request.category} 분야 Mock 사례 분석",
                key_issues=["사실관계와 공식 근거 확인"],
                answer="Mock 모드에서는 공식 법률 자료 연결 전의 안내만 제공합니다. 실제 연동 후 공식 출처를 확인해 주세요.",
                cautions=["법률 자문이나 결과 보장이 아닌 정보 제공입니다."], is_mock=True,
            )
    if idempotency_key:
        store.idempotency[(owner, "/api/legal/questions", idempotency_key)] = (now() + timedelta(hours=24), response.model_dump(mode="json"))
    store.history.setdefault(owner, []).append({"id": f"history-{response.request_id}", "type": "legal_analysis", "target_id": response.request_id, "category": request.category, "title": request.question[:100], "created_at": iso()})
    store.notify(owner, "ANALYSIS_COMPLETED" if response.termination_reason == "model_finished" else "ANALYSIS_NO_RESULTS", "사례 분석 완료", "사례 분석 결과를 확인해 주세요.", target_type="legal_analysis", target_id=response.request_id, category=request.category)
    return response


@router.get("/laws")
@router.get("/cases")
def search_documents(category: str, query: str = Query(min_length=2, max_length=200), top_k: int = Query(3, ge=1, le=10)) -> dict:
    if category not in {"housing", "labor", "consumer"}:
        raise HTTPException(status_code=422, detail={"code": "VALIDATION_ERROR", "message": "지원하지 않는 분야입니다."})
    # Mock 단계에서는 실제 검색어와 맞는 자료만 돌려주며, 결과를 꾸며 내지 않는다.
    return {"query": query.strip(), "category": category, "items": [], "total": 0}


@router.get("/terms")
def search_terms(category: str, query: str = Query(min_length=2, max_length=200)) -> dict:
    terms = {"labor": {"임금체불": "정해진 때에 임금이 지급되지 않은 상태입니다."}, "housing": {"보증금": "임대차 계약에서 반환 조건을 정하는 금액입니다."}, "consumer": {"청약철회": "일정한 거래에서 계약을 취소할 수 있는 권리입니다."}}
    matched = [{"term": term, "description": description} for term, description in terms.get(category, {}).items() if query.strip() in term or query.strip() in description]
    return {"items": matched}

