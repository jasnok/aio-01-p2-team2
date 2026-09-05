from copy import deepcopy
from uuid import uuid4

from frontend.data.categories import get_category
from frontend.data.mock_catalog import MOCK_CATALOG


class MockLegalService:
    """Backend 없이 UI 흐름을 검증하는 결정적 Local Service."""

    def analyze_case(self, category: str, question: str) -> dict:
        get_category(category)
        if len(question.strip()) < 5:
            raise ValueError("사례를 5자 이상 입력해 주세요.")
        catalog = MOCK_CATALOG[category]
        return {
            "request_id": f"local-{uuid4()}",
            "agent_id": category,
            "status": "completed",
            "termination_reason": "mock_finished",
            "question_summary": catalog["summary"],
            "key_issues": deepcopy(catalog["issues"]),
            "answer": catalog["answer"],
            "related_laws": deepcopy(catalog["laws"]),
            "similar_cases": deepcopy(catalog["cases"]),
            "follow_up_questions": ["정확한 계약일·거래일·퇴직일은 언제인가요?", "상대방에게 요청한 기록이 있나요?"],
            "cautions": ["화면 확인용 예시 결과이며 실제 법률 판단이나 법률 자문이 아닙니다."],
            "is_mock": True,
            "question": question.strip(),
        }

    def search_laws(self, category: str, query: str) -> list[dict]:
        return self._search(category, query, "laws")

    def search_cases(self, category: str, query: str) -> list[dict]:
        return self._search(category, query, "cases")

    def search_terms(self, category: str, query: str) -> list[tuple[str, str]]:
        get_category(category)
        normalized = query.strip().lower()
        terms = MOCK_CATALOG[category]["terms"]
        if not normalized:
            return deepcopy(terms)
        return [deepcopy(item) for item in terms if normalized in f"{item[0]} {item[1]}".lower()]

    @staticmethod
    def _search(category: str, query: str, key: str) -> list[dict]:
        get_category(category)
        normalized = query.strip().lower()
        if len(normalized) < 2:
            raise ValueError("검색어를 2자 이상 입력해 주세요.")
        results = []
        for item in MOCK_CATALOG[category][key]:
            searchable = " ".join(str(value) for value in (item.get("title"), item.get("article"), *item.get("keywords", []))).lower()
            if normalized in searchable or any(token in searchable for token in normalized.split()):
                results.append(deepcopy(item))
        return results[:3]
