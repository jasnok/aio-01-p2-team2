from copy import deepcopy

from frontend.clients import backend_client
from frontend.data.categories import get_category


def _source_label(item: dict) -> str:
    source = item.get("source") or {}
    return source.get("url") or source.get("title") or "공식 출처 확인 필요"


def _law_view(item: dict) -> dict:
    metadata = item.get("metadata") or {}
    summary = item.get("summary") or item.get("content") or "요약이 없습니다."
    return {
        **deepcopy(item),
        "title": item.get("law_name") or item.get("title") or "법령 정보",
        "article": item.get("article_number") or metadata.get("article") or "조문 정보 없음",
        "summary": summary,
        "detail": item.get("content") or summary,
        "source": _source_label(item),
    }


def _case_view(item: dict) -> dict:
    return {
        **deepcopy(item),
        "title": item.get("case_name") or item.get("title") or "판례 정보",
        "court": item.get("court") or "법원 정보 없음",
        "score": item.get("score") or 0,
        "case_number": item.get("case_number") or "사건번호 없음",
        "date": str(item.get("decided_at") or "선고일 정보 없음"),
        "result": item.get("judgment_result") or item.get("summary") or "판결 결과 확인 필요",
        "points": deepcopy(item.get("similar_points") or []),
        "source": _source_label(item),
    }


class ApiLegalService:
    """Backend API 응답을 기존 Frontend View Model로 변환한다."""

    def __init__(self, session_id: str):
        self.session_id = session_id

    def analyze_case(self, category: str, question: str, *, scenario: str = "success") -> dict:
        get_category(category)
        if len(question.strip()) < 5:
            raise ValueError("사례를 5자 이상 입력해 주세요.")
        try:
            result = backend_client.ask_legal_question(category, question.strip(), self.session_id, scenario=scenario)
        except backend_client.BackendClientError as error:
            raise ValueError(error.user_message) from error
        result["related_laws"] = [_law_view(item) for item in result.get("related_laws", [])]
        result["similar_cases"] = [_case_view(item) for item in result.get("similar_cases", [])]
        result["question"] = question.strip()
        result.setdefault("consultations", [])
        result["result_state"] = "completed" if any(result.get(key) for key in ("related_laws", "similar_cases", "consultations")) else "no_results"
        return result

    def search_laws(self, category: str, query: str) -> list[dict]:
        self._validate_search(category, query)
        try:
            payload = backend_client.search_laws(category, query.strip())
        except backend_client.BackendClientError as error:
            raise ValueError(error.user_message) from error
        return [_law_view(item) for item in payload.get("items", [])]

    def search_cases(self, category: str, query: str) -> list[dict]:
        self._validate_search(category, query)
        try:
            payload = backend_client.search_cases(category, query.strip())
        except backend_client.BackendClientError as error:
            raise ValueError(error.user_message) from error
        return [_case_view(item) for item in payload.get("items", [])]

    def search_terms(self, category: str, query: str) -> list[tuple[str, str]]:
        get_category(category)
        try:
            if not query.strip():
                payload = backend_client.get_category_catalog(category)
                return [tuple(item) for item in payload.get("terms", [])]
            if len(query.strip()) < 2:
                return []
            payload = backend_client.search_terms(category, query.strip())
        except backend_client.BackendClientError as error:
            raise ValueError(error.user_message) from error
        return [(item["term"], item["description"]) for item in payload.get("items", [])]

    @staticmethod
    def _validate_search(category: str, query: str) -> None:
        get_category(category)
        if len(query.strip()) < 2:
            raise ValueError("검색어를 2자 이상 입력해 주세요.")
