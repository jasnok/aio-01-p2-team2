import httpx
import hashlib
from pydantic import ValidationError

from frontend.core.config import get_frontend_settings
from frontend.core.models import LegalQuestionView, SearchResultsView


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
        if response.status_code == 204 or not response.content:
            return {}
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
    if isinstance(detail, list):
        return "VALIDATION_ERROR", "입력 내용을 확인해 주세요. 검색어는 2~200자입니다."
    if isinstance(detail, dict):
        return detail.get("code", "BACKEND_ERROR"), detail.get("message", "Backend 요청에 실패했습니다.")
    return "BACKEND_ERROR", str(detail)


def get_backend_health() -> dict:
    return _request("GET", "/health")


def get_mcp_integration_status() -> dict:
    return _request("GET", "/api/integration/mcp")


def search_food_mock(
    region: str = "서울",
    food_category: str = "한식",
    max_price: int = 20000,
    allergy: str = "없음",
    limit: int = 3,
) -> dict:
    return _request(
        "POST",
        "/api/integration/mcp/food-search",
        json={
            "region": region,
            "food_category": food_category,
            "max_price": max_price,
            "allergy": allergy,
            "limit": limit,
        },
    )


def ask_legal_question(category: str, question: str, session_id: str, *, scenario: str = "success") -> dict:
    idempotency_source = f"{session_id}:{category}:{question}".encode("utf-8")
    headers = {
        "Idempotency-Key": hashlib.sha256(idempotency_source).hexdigest(),
        "X-Guest-Id": session_id,
    }
    if scenario != "success":
        headers["X-Mock-Scenario"] = scenario
    payload = _request(
        "POST",
        "/api/legal/questions",
        json={"session_id": session_id, "category": category, "question": question},
        headers=headers,
    )
    try:
        return LegalQuestionView.model_validate(payload).model_dump(mode="json")
    except ValidationError as error:
        raise BackendClientError("Backend 응답 형식이 Frontend 계약과 다릅니다.", "CONTRACT_MISMATCH") from error


def search_laws(category: str, query: str, top_k: int = 3) -> dict:
    return _search_documents("laws", "law", category, query, top_k)


def search_cases(category: str, query: str, top_k: int = 3) -> dict:
    return _search_documents("cases", "case", category, query, top_k)


def search_consultations(category: str, query: str, top_k: int = 3) -> dict:
    return _search_documents("consultations", "consultation", category, query, top_k)


def _search_documents(kind: str, source_type: str, category: str, query: str, top_k: int) -> dict:
    query = query.strip()
    if category not in {"housing", "labor", "consumer"} or not 2 <= len(query) <= 200 or not 1 <= top_k <= 10:
        raise BackendClientError("카테고리와 검색어(2~200자)를 확인해 주세요.", "VALIDATION_ERROR")
    payload = _request("GET", f"/api/legal/{kind}", params={"category": category, "query": query, "top_k": top_k})
    try:
        result = SearchResultsView.model_validate(payload)
        if (result.category != category or result.query != query
                or result.total != len(result.items) or len(result.items) > top_k
                or result.is_mock
                or any(item.source.source_type != source_type for item in result.items)):
            raise ValueError("검색 응답 내용 불일치")
        return result.model_dump(mode="json")
    except (ValidationError, ValueError) as error:
        raise BackendClientError("검색 API 응답이 확정 계약과 다릅니다. 백엔드 배포 상태를 확인해 주세요.", "CONTRACT_MISMATCH") from error


def search_terms(category: str, query: str) -> dict:
    return _request("GET", "/api/legal/terms", params={"category": category, "query": query})


def get_category_catalog(category: str) -> dict:
    return _request("GET", f"/api/catalog/{category}")


def auth_headers(token: str | None, guest_id: str) -> dict[str, str]:
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {"X-Guest-Id": guest_id}


def register(email: str, password: str, display_name: str) -> dict:
    return _request("POST", "/api/auth/register", json={"email": email, "password": password, "display_name": display_name})


def login(email: str, password: str) -> dict:
    return _request("POST", "/api/auth/login", json={"email": email, "password": password})


def logout(token: str) -> None:
    _request("POST", "/api/auth/logout", headers=auth_headers(token, ""))


def request_password_reset(email: str) -> dict:
    return _request("POST", "/api/auth/password-reset", json={"email": email})


def get_current_user(token: str | None, guest_id: str) -> dict:
    return _request("GET", "/api/auth/me", headers=auth_headers(token, guest_id))


def list_faqs(category: str | None = None) -> dict:
    params = {"category": category} if category else None
    return _request("GET", "/api/faqs", params=params)


def create_admin_faq(token: str, body: dict) -> dict:
    return _request("POST", "/api/admin/faqs", json=body, headers=auth_headers(token, ""))


def list_admin_faqs(token: str) -> dict:
    return _request("GET", "/api/admin/faqs", headers=auth_headers(token, ""))


def update_admin_faq(token: str, faq_id: str, body: dict) -> dict:
    return _request("PATCH", f"/api/admin/faqs/{faq_id}", json=body, headers=auth_headers(token, ""))


def delete_admin_faq(token: str, faq_id: str) -> None:
    _request("DELETE", f"/api/admin/faqs/{faq_id}", headers=auth_headers(token, ""))


def list_questions(token: str | None, guest_id: str, **params) -> dict:
    return _request("GET", "/api/questions", params=params, headers=auth_headers(token, guest_id))


def create_question_api(token: str | None, guest_id: str, body: dict) -> dict:
    return _request("POST", "/api/questions", json=body, headers=auth_headers(token, guest_id))


def get_question(token: str | None, guest_id: str, question_id: str) -> dict:
    return _request("GET", f"/api/questions/{question_id}", headers=auth_headers(token, guest_id))


def unlock_question(token: str | None, guest_id: str, question_id: str, password: str) -> dict:
    return _request("POST", f"/api/questions/{question_id}/unlock", json={"post_password": password}, headers=auth_headers(token, guest_id))


def update_question_api(token: str | None, guest_id: str, question_id: str, body: dict) -> dict:
    return _request("PATCH", f"/api/questions/{question_id}", json=body, headers=auth_headers(token, guest_id))


def delete_question_api(token: str | None, guest_id: str, question_id: str, password: str, *, reason: str | None = None) -> None:
    # 관리자는 삭제 사유만으로 권한을 검증하고, 작성자 삭제만 게시글
    # 비밀번호를 사용한다. 빈 비밀번호를 보내면 Backend Schema에서 422가 난다.
    body = {"reason": reason} if reason else {"post_password": password}
    _request("DELETE", f"/api/questions/{question_id}", json=body, headers=auth_headers(token, guest_id))


def resubmit_question(token: str | None, guest_id: str, question_id: str, password: str) -> dict:
    return _request("POST", f"/api/questions/{question_id}/resubmit", json={"post_password": password}, headers=auth_headers(token, guest_id))


def list_comments(token: str | None, guest_id: str, question_id: str, page: int = 1) -> dict:
    return _request("GET", f"/api/questions/{question_id}/comments", params={"page": page, "page_size": 20}, headers=auth_headers(token, guest_id))


def create_comment_api(token: str | None, guest_id: str, question_id: str, content: str, password: str | None) -> dict:
    return _request("POST", f"/api/questions/{question_id}/comments", json={"content": content, "comment_password": password}, headers=auth_headers(token, guest_id))


def update_comment_api(token: str | None, guest_id: str, question_id: str, comment_id: str, content: str, password: str | None) -> dict:
    return _request("PATCH", f"/api/questions/{question_id}/comments/{comment_id}", json={"content": content, "comment_password": password}, headers=auth_headers(token, guest_id))


def delete_comment_api(token: str | None, guest_id: str, question_id: str, comment_id: str, password: str | None) -> None:
    # Backend v1.2가 삭제 Body에도 CommentBody를 재사용하므로 검증용 content를 함께 보낸다.
    _request("DELETE", f"/api/questions/{question_id}/comments/{comment_id}", json={"content": "삭제 요청", "comment_password": password}, headers=auth_headers(token, guest_id))


def list_history(token: str | None, guest_id: str, **params) -> dict:
    return _request("GET", "/api/history", params=params, headers=auth_headers(token, guest_id))


def delete_history(token: str | None, guest_id: str, history_id: str) -> None:
    _request("DELETE", f"/api/history/{history_id}", headers=auth_headers(token, guest_id))


def list_notifications(token: str | None, guest_id: str, page_size: int = 20) -> dict:
    return _request("GET", "/api/notifications", params={"page": 1, "page_size": page_size}, headers=auth_headers(token, guest_id))


def get_unread_count(token: str | None, guest_id: str) -> int:
    return _request("GET", "/api/notifications/unread-count", headers=auth_headers(token, guest_id)).get("count", 0)


def mark_notification_read(token: str | None, guest_id: str, notification_id: str) -> dict:
    return _request("PATCH", f"/api/notifications/{notification_id}/read", headers=auth_headers(token, guest_id))


def mark_notifications_read(token: str | None, guest_id: str) -> dict:
    return _request("PATCH", "/api/notifications/read-all", headers=auth_headers(token, guest_id))


def delete_notification_api(token: str | None, guest_id: str, notification_id: str) -> None:
    _request("DELETE", f"/api/notifications/{notification_id}", headers=auth_headers(token, guest_id))


def delete_read_notifications_api(token: str | None, guest_id: str) -> None:
    _request("DELETE", "/api/notifications/read-items", headers=auth_headers(token, guest_id))


# Agent 진행 상태 API 계약 준비. Backend 구현 후 polling부터 연결하고,
# 안정화 뒤 /events SSE로 전환한다.
def create_agent_run(token: str | None, guest_id: str, category: str, question: str, idempotency_key: str) -> dict:
    return _request(
        "POST",
        "/api/agent-runs",
        json={"category": category, "question": question},
        headers={**auth_headers(token, guest_id), "Idempotency-Key": idempotency_key},
    )


def get_agent_run(token: str | None, guest_id: str, run_id: str) -> dict:
    return _request("GET", f"/api/agent-runs/{run_id}", headers=auth_headers(token, guest_id))


def cancel_agent_run(token: str | None, guest_id: str, run_id: str) -> dict:
    return _request("POST", f"/api/agent-runs/{run_id}/cancel", headers=auth_headers(token, guest_id))
