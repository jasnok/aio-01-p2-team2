from dataclasses import dataclass


WORKFLOW_STEPS = (
    ("validate", "질문 검증"),
    ("route", "담당 Agent 선택"),
    ("search_laws", "관련 법령 검색"),
    ("search_cases", "유사 판례 검색"),
    ("validate_evidence", "공식 근거 검증"),
    ("generate", "답변 생성"),
)

MOCK_SCENARIOS = {
    "success": "정상 완료",
    "no_results": "검색 결과 없음",
    "no_evidence": "공식 근거 부족",
    "backend_error": "Backend 연결 실패",
    "mcp_error": "MCP 연결 실패",
    "db_error": "DB 연결 실패",
    "timeout": "응답 시간 초과",
    "invalid_response": "응답 형식 오류",
    "cancelled": "사용자 취소",
}


@dataclass(frozen=True)
class MockScenarioError(Exception):
    code: str
    stage: str
    user_message: str
    next_action: str
    retryable: bool = True

    def __str__(self) -> str:
        return self.user_message


def scenario_error(scenario: str) -> MockScenarioError | None:
    errors = {
        "backend_error": MockScenarioError("BACKEND_UNAVAILABLE", "Backend 연결", "Backend에 연결하지 못했습니다.", "잠시 후 다시 시도하거나 팀 서버 상태를 확인해 주세요."),
        "mcp_error": MockScenarioError("MCP_UNAVAILABLE", "판례 검색", "법률 검색 도구에 연결하지 못했습니다.", "MCP 서버 상태를 확인한 뒤 다시 시도해 주세요."),
        "db_error": MockScenarioError("DB_UNAVAILABLE", "법률 자료 조회", "법률 자료를 불러오지 못했습니다.", "DB 연결 상태를 확인한 뒤 다시 시도해 주세요."),
        "timeout": MockScenarioError("REQUEST_TIMEOUT", "답변 생성", "처리 시간이 예상보다 길어 중단했습니다.", "질문을 조금 더 구체적으로 작성해 다시 시도해 주세요."),
        "invalid_response": MockScenarioError("INVALID_RESPONSE", "결과 확인", "응답 형식이 화면 계약과 맞지 않습니다.", "개발자에게 오류 코드를 전달해 주세요.", False),
        "cancelled": MockScenarioError("USER_CANCELLED", "실행 취소", "사용자가 분석을 취소했습니다.", "원할 때 다시 분석할 수 있습니다.", False),
    }
    return errors.get(scenario)
