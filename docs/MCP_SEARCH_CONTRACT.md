# MCP 검색 응답 계약

## 실제 문제

기존 Runtime은 `payload.get("data") or []`를 사용했다. `{"success": true, "data": {}}`를 단일 검색에 주입하면 잘못된 응답이 `completed / no_results`로 종료됐다. 통합 검색은 빈 객체나 누락한 items도 빈 결과로 바꾸고, 근거 항목의 스키마는 진행 이벤트 이후에야 검사될 수 있었다. MCP transport의 structuredContent 경로도 text JSON 경로와 달리 객체 여부를 검사하지 않았다.

## 변경

단일·병렬 검색은 `search_evidence` 공통 경계에서 검사한다.

| 항목 | 계약 |
| --- | --- |
| 응답 | JSON 객체이며 success는 명시적인 boolean |
| 성공한 개별 검색 | data가 근거 배열 |
| 성공한 통합 검색 | data가 객체이고 items가 근거 배열 |
| 근거 항목 | backend Evidence 스키마에 맞는 객체 |
| 자료 유형 | 법령=law, 판례=case, 상담=consultation, 통합=law 또는 case |
| 빈 결과 | 실제 빈 배열만 정상 검색 결과 없음 |
| 실패 | 고정 메시지의 RuntimeError; 외부 오류 본문 제외 |
| 계약 위반 | 고정 메시지의 SearchContractError; 응답 본문 제외 |

계약 위반은 해당 도구의 tool_completed 이벤트 전에 실패한다. 병렬 검색의 기존 finally 정리는 남은 작업을 취소하고 기다린다. 정상적인 다른 도구가 먼저 완료됐다면 그 진행 이벤트는 이미 전달될 수 있으나, 전체 검색은 완료 상태나 생성 단계로 넘어가지 않는다.

Pydantic 검사 뒤 원본 근거 딕셔너리를 반환해 확장 metadata와 기존 표현을 보존한다. 서버의 기존 검색 순서와 중복 제거, 도구 허용 정책, 검색 병렬화는 유지한다. MCP transport는 structuredContent가 있으면 그 값을 우선하며 JSON 객체인지 검사한다. 빈 structured 객체를 text로 대신하지 않는다. text 경로는 빈 응답·비JSON·배열 등을 거부한다.

## 검증과 한계

합성 응답으로 success 누락/잘못된 타입, data/items 누락·null·잘못된 타입, 불완전한 근거, 다른 자료 유형, 실제 빈 배열, 정상 근거의 metadata 보존, 잘못된 검색의 병렬 형제 작업 취소, structured/text transport 계약을 검사했다. 기존 병렬 시작·결과 순서와 검색 API 테스트도 실행했다.

이 검사는 응답 형식과 자료 유형에 대한 검증이다. 검색 관련성, 법적 정확성, 출처 URL 신뢰성이나 모델 품질을 보증하지 않는다. 실제 모델 호출·embedding 요청 없이 검증했으며 속도 향상 수치는 측정하지 않았다. 도구 성공 응답의 null data를 과거처럼 빈 결과로 처리하지 않으므로 외부 서버가 계약을 어기면 안전한 API 오류로 드러난다.
