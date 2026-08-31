from fastapi import APIRouter, HTTPException

from backend.app.schemas.legal import LegalQuestionRequest, LegalQuestionResponse
from backend.app.services.legal_question_service import answer_question


router = APIRouter(prefix="/api/legal", tags=["legal"])


@router.post("/questions", response_model=LegalQuestionResponse)
def create_question(request: LegalQuestionRequest) -> LegalQuestionResponse:
    try:
        return answer_question(request)
    except Exception as error:
        raise HTTPException(status_code=502, detail={"code": "MCP_UNAVAILABLE", "message": str(error)}) from error

