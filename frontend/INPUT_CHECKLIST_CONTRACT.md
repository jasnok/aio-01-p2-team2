# 백엔드 입력 체크리스트 추가 요청

기존 분석 결과의 `input_assessment.status`, `message`와 결과 영역 안내는 유지합니다.
동일한 Agent 판단에서 아래 선택 객체 `checks`를 추가해 주세요. 새 API/SSE 이벤트는 필요 없습니다.

```json
{
  "input_assessment": {
    "status": "proceed_with_caution",
    "message": "일반적인 검색은 가능하지만 추가 확인이 필요합니다.",
    "checks": {
      "situation": "met",
      "timing": "not_required",
      "relationship": "met",
      "request_evidence": "missing"
    }
  }
}
```

- 예시는 스키마 설명용이며 특정 질문에 대한 실제 판단이 아닙니다.
- 키: situation(구체적인 상황), timing(시점·기간), relationship(상대방·관계), request_evidence(요청·증거).
- 값: met(확인됨), missing(추가 확인 필요), not_required(이 질문에는 필요하지 않음).
- checks는 누락/null 허용. 객체를 보낼 때는 네 항목을 모두 반환합니다.
- 키워드가 아닌 질문 의미와 요청 목적에 따라 판단합니다. 날짜·증거가 모든 검색의 필수조건은 아닙니다.
- 전체 진행 여부는 기존 status 판단을 따릅니다. 체크 개수로 검색을 차단하지 않습니다.
- 동일한 결과를 동기 응답 및 SSE 최종 실행 스냅샷에 저장합니다. 기존 stopped/input.required 계약을 유지합니다.
- 프론트엔드는 met 개수/적용 대상 개수로 표시하고 not_required 개수는 별도로 표시합니다.
- 프론트엔드는 입력과 응답의 질문·카테고리가 다르면 이전 체크 결과를 숨깁니다.
- 필드가 없으면 미제공 안내만 표시하며 체크 결과를 생성하지 않습니다.
- 입력 도중 추가 API 호출은 하지 않습니다. 최초 판단은 분석 요청 후 표시됩니다.
- MCP/DB 변경은 이번 계약에 필요하지 않습니다.

검증 요청: 일반 조문 질문의 불필요한 정보는 not_required, 모호한 질문은 보완 질문,
이미 명시한 정보는 met, 동기/SSE 동일 결과, 형식 검증 및 기존 검색 흐름 회귀를 확인해 주세요.
