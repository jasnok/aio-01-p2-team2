import logging

from fastapi import APIRouter, Depends, HTTPException

from backend.app.repositories.saved_conversation_repository import SavedConversationNotFoundError
from backend.app.routers.mock_api import actor, require_user
from backend.app.schemas.legal_terms import LegalTermChatRequest, LegalTermChatResponse
from backend.app.services.guest_session_service import guest_sessions
from backend.app.services.legal_term_chat_service import LegalTermChatService
from backend.app.services.legal_term_run_store import LegalTermRunForbiddenError, LegalTermRunNotFoundError, legal_term_runs
from backend.app.services.saved_conversation_service import SavedConversationService
from backend.app.services.session_service import SessionStoreUnavailableError


router = APIRouter(prefix="/api/legal-terms", tags=["legal-terms"])
term_run_router = APIRouter(prefix="/api/legal-term-runs", tags=["legal-terms"])
logger = logging.getLogger(__name__)
term_chat_service = LegalTermChatService()
saved_conversation_service = SavedConversationService()


@router.post("/chat", response_model=LegalTermChatResponse, summary="쉬운 법률 용어 대화")
async def chat_with_legal_terms(
    body: LegalTermChatRequest,
    value: dict = Depends(actor),
) -> LegalTermChatResponse:
    try:
        if value["role"] == "GUEST":
            context = await guest_sessions.term_context(str(value["id"]))
        elif body.conversation_id is not None:
            context = await saved_conversation_service.build_term_context_for_actor(
                actor=value, conversation_id=body.conversation_id,
            )
        else:
            context = []
    except SavedConversationNotFoundError as error:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "저장한 법률 용어 대화를 찾을 수 없습니다."}) from error
    except SessionStoreUnavailableError as error:
        raise HTTPException(status_code=503, detail={"code": "GUEST_SESSION_UNAVAILABLE", "message": "비회원 임시 대화를 불러올 수 없습니다."}) from error

    try:
        response = await term_chat_service.chat(body.message, context)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail={"code": "LLM_UNAVAILABLE", "message": "법률 용어 대화 서비스를 사용할 수 없습니다."}) from error

    try:
        await legal_term_runs.remember(
            actor=value,
            request_id=response.request_id,
            question=body.message,
            answer=response.answer,
            conversation_id=body.conversation_id,
        )
    except SessionStoreUnavailableError as error:
        raise HTTPException(status_code=503, detail={"code": "TERM_RUN_UNAVAILABLE", "message": "저장할 법률 용어 대화 결과를 준비하지 못했습니다."}) from error

    if value["role"] == "GUEST":
        try:
            await guest_sessions.save_term_chat(str(value["id"]), {
                "run_id": response.request_id,
                "question": body.message,
                "status": "completed",
                "result": {"answer": response.answer, "related_terms": response.related_terms},
            })
        except SessionStoreUnavailableError as error:
            raise HTTPException(status_code=503, detail={"code": "GUEST_SESSION_UNAVAILABLE", "message": "비회원 임시 대화를 저장할 수 없습니다."}) from error
        return response.model_copy(update={"storage": "guest_temporary"})

    if not body.save_selected:
        return response
    try:
        conversation_id = await saved_conversation_service.save_term_chat(
            actor=value, question=body.message, answer=response.answer,
            request_id=response.request_id, conversation_id=body.conversation_id,
        )
    except SavedConversationNotFoundError as error:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "저장한 법률 용어 대화를 찾을 수 없습니다."}) from error
    except Exception as error:
        logger.exception("legal_term_chat_save_failed request_id=%s", response.request_id)
        raise HTTPException(status_code=503, detail={"code": "SAVED_CONVERSATION_UNAVAILABLE", "message": "법률 용어 대화를 저장할 수 없습니다."}) from error
    return response.model_copy(update={"conversation_id": conversation_id, "saved": True, "storage": "member"})


@term_run_router.post("/{request_id}/save", summary="법률 용어 대화 결과 저장")
async def save_legal_term_run(request_id: str, value: dict = Depends(require_user)) -> dict:
    try:
        run = await legal_term_runs.get_for_actor(request_id, value)
        conversation_id = await saved_conversation_service.save_term_chat(
            actor=value,
            question=run["question"],
            answer=run["answer"],
            request_id=run["request_id"],
            conversation_id=run["conversation_id"],
        )
    except LegalTermRunNotFoundError:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "저장할 법률 용어 대화 결과를 찾을 수 없습니다."})
    except LegalTermRunForbiddenError:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "다른 회원의 법률 용어 대화 결과는 저장할 수 없습니다."})
    except SessionStoreUnavailableError as error:
        raise HTTPException(status_code=503, detail={"code": "TERM_RUN_UNAVAILABLE", "message": "법률 용어 대화 결과를 불러올 수 없습니다."}) from error
    except Exception as error:
        logger.exception("legal_term_run_save_failed request_id=%s", request_id)
        raise HTTPException(status_code=503, detail={"code": "SAVED_CONVERSATION_UNAVAILABLE", "message": "법률 용어 대화를 저장할 수 없습니다."}) from error
    return {"conversation_id": conversation_id, "saved": True}
