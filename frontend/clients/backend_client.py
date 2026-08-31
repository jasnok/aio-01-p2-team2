import httpx
from pydantic import ValidationError

from frontend.core.config import get_frontend_settings
from frontend.core.models import LegalQuestionView


ERROR_MESSAGES = {
    "INVALID_REQUEST": "입력 내용을 확인해 주세요.",
    "UNSUPPORTED_CATEGORY": "현재 지원하지 않는 법률 카테고리입니다.",
    "MCP_UNAVAILABLE": "법률 검색 서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.",
    "TOOL_VALIDATION_ERROR": "검색 요청을 구성하지 못했습니다. 질문을 조금 더 구체적으로 작성해 주세요.",
    "NO_RELEVANT_EVIDENCE": "관련성이 충분한 법률 자료를 찾지 못했습니다.",
    "LLM_TIMEOUT": "답변 생성 시간이 초과되었습니다. 다시 시도해 주세요.",
}


class BackendClientError(RuntimeError):
    def __init__(self, user_message: str, code: str | None = None):
        super().__init__(user_message)
        self.user_message = user_message
        self.code = code


def _request(method: str, path: str, **kwargs) -> dict:
    settings = get_frontend_settings()
    try:
        response = httpx.request(
            method,
            f"{settings.normalized_backend_url}{path}",
            timeout=settings.frontend_request_timeout_seconds,
            **kwargs,
        )
        response.raise_for_status()
        return response.json()
    except httpx.TimeoutException as error:
        raise BackendClientError("Backend 응답 시간이 초과되었습니다.", "BACKEND_TIMEOUT") from error
    except httpx.ConnectError as error:
        raise BackendClientError("Backend에 연결할 수 없습니다. 서버 주소와 실행 상태를 확인해 주세요.", "BACKEND_UNAVAILABLE") from error
    except httpx.HTTPStatusError as error:
        code, message = _extract_api_error(error.response)
        raise BackendClientError(ERROR_MESSAGES.get(code, message), code) from error
    except (ValueError, TypeError) as error:
        raise BackendClientError("Backend가 올바른 JSON 응답을 반환하지 않았습니다.", "INVALID_RESPONSE") from error


def _extract_api_error(response: httpx.Response) -> tuple[str, str]:
    try:
        payload = response.json()
    except ValueError:
        return "BACKEND_ERROR", f"Backend 요청에 실패했습니다. HTTP {response.status_code}"

    detail = payload.get("detail", payload)
    if isinstance(detail, dict):
        return detail.get("code", "BACKEND_ERROR"), detail.get("message", "Backend 요청에 실패했습니다.")
    return "BACKEND_ERROR", str(detail)


def get_backend_health() -> dict:
    return _request("GET", "/health")


def ask_legal_question(category: str, message: str, session_id: str) -> dict:
    payload = _request(
        "POST",
        "/api/legal/questions",
        json={"session_id": session_id, "category": category, "message": message},
    )
    try:
        return LegalQuestionView.model_validate(payload).model_dump(mode="json")
    except ValidationError as error:
        raise BackendClientError("Backend 응답 형식이 Frontend 계약과 다릅니다.", "CONTRACT_MISMATCH") from error
