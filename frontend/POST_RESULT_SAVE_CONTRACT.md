# 결과 확인 후 저장 · 프론트엔드 확정 계약

프론트엔드가 채택한 계약입니다. 백엔드 배포 일치와 실제 DB 반영은 별도 확인이 필요합니다.

## 저장 API

- POST /api/agent-runs/{run_id}/save: 완료된 분석 결과 저장
- POST /api/legal-term-runs/{request_id}/save: 해당 요청의 사용자 질문과 답변 한 쌍 저장
- Authorization: Bearer <token> 필수. 요청 본문 없음.
- 성공: HTTP 200, `{"saved":true,"conversation_id":123}`
- saved는 JSON boolean, conversation_id는 양의 정수. 중복 호출도 동일 ID를 반환하며 새 레코드를 만들지 않습니다.
- 실패는 401 인증 만료, 403 소유권 없음, 404 결과 없음/만료, 409 미완료 결과 등으로 반환합니다.
- 결과 생성이나 LLM 호출을 다시 실행하지 않고 서버에 보관된 원래 결과를 저장합니다.
- 미저장 회원 결과도 저장 버튼을 누를 때 조회 가능하도록 보관해야 합니다.

## ID 보존

- 분석 시작 응답의 run_id를 프론트엔드 최종 결과와 연결합니다.
- POST /api/legal-terms/chat 응답은 request_id(string, 필수), answer(string), conversation_id(int|null), saved(bool), storage를 반환합니다.
- request_id는 질문마다 고유하고, 용어 대화의 conversation_id와 저장 이력 ID를 혼동하지 않습니다.
- 질문 시 save_selected=false. 이후 답변마다 저장 버튼을 제공합니다. 이전 대화 전체를 자동 저장하지 않습니다.
- 현재 질문 message에는 분석 문맥이 포함됩니다. 저장 시 이를 질문 원문으로 보관하는 현 구조를 지원하며 별도 깨끗한 사용자 입력 필드가 필요하면 후속 협의합니다.

## 통합 저장 이력

GET /api/saved-conversations?page=1&page_size=20

```json
{"items":[{"id":123,"type":"legal_terms","title":"할부항변권 설명","question":"할부항변권이 무엇인가요?","summary":"용어 설명","created_at":"2026-09-09T06:00:00Z"}],"page":1,"page_size":20,"total":1}
```

- id는 저장 성공의 conversation_id와 동일합니다. type은 analysis 또는 legal_terms 필수입니다.
- 최신순 정렬. 현재 프론트엔드 유형 선택은 현재 페이지에서 필터합니다.
- GET /api/saved-conversations/{conversation_id}: 위 항목 필드에 상세 필드를 추가해 직접 반환합니다(별도 data 래퍼 없음).
- analysis 상세: result에 기존 LegalQuestion 응답 전체, question에 원래 질문.
- legal_terms 상세: messages에 `[{"role":"user","content":"질문"},{"role":"assistant","content":"답변"}]` 시간순 반환. created_at은 선택.
- DELETE /api/saved-conversations/{conversation_id}: HTTP 204. 두 유형 동일 경로 사용.
- 조회/저장은 소유 회원만 허용합니다.

## 비회원

- 저장 버튼 숨김. X-Guest-Id로 GET /api/guest/temporary-history 사용.
- items는 위와 같은 type을 포함하고 상세(result 또는 messages)도 포함합니다.
- expires_at은 시간대 포함 ISO8601, expires_in은 초 단위 선택 필드입니다.
- DELETE /api/guest/temporary-history는 해당 Guest ID의 임시 이력을 전체 삭제하고 HTTP 204 반환합니다.

## 검증 상태

저장 경로 두 개의 Swagger 등록은 확인했습니다. 응답 필드, 중복 저장, 소유권 및 실제 DB 저장은 아직 실행 검증하지 않았습니다. 사용자가 직접 테스트하기로 하여 자동 시험은 실행하지 않았습니다.
