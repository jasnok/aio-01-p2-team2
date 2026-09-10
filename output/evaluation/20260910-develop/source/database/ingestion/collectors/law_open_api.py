"""
법령명 목록 조회
법령 ID 선택
법령 상세본문 조회
응답 오류 확인
원본 XML 반환
"""

def search_current_law(
    law_name: str,
) -> list[dict]:
    """현행법령 목록에서 정확한 법령명을 검색합니다."""


def select_exact_law(
    results: list[dict],
    law_name: str,
) -> dict:
    """검색 결과에서 이름이 정확히 같은 현행 법령을 선택합니다."""


def fetch_current_law_xml(
    law_id: str,
) -> str:
    """선택한 법령 ID로 전체본문 XML을 조회합니다."""