# 포트폴리오 문서 색인

처음 검토할 때는 [담당 범위·설계 선택·3분 시연](PORTFOLIO_CASE_STUDY.md)을 읽고, [Docker 실행 안내](DOCKER_LOCAL_SETUP.md)로 사이트를 실행한다. 아래 기록은 구현 당시의 검증과 한계를 담는다. 과거 문서의 테스트 개수나 측정값은 현재 전체 코드의 결과로 해석하지 않는다.

[main CI 실행 목록](https://github.com/jasnok/aio-01-p2-team2/actions/workflows/test.yml?query=branch%3Amain) · [개선 PR 기록](https://github.com/jasnok/aio-01-p2-team2/pulls?q=is%3Apr+is%3Amerged+base%3Amain)

## 설계·실행·평가 계획

- [3차 평가·문맥 보존·주장 검증 구현과 5~6단계 세부 계획](PORTFOLIO_PHASE3_AND_ROADMAP.md)
- [다음 응답 속도 개선과 코드 단순화 계획](LATENCY_AND_SIMPLIFICATION_PLAN.md)
- [응답 속도 실험과 비동기 호출·답변 흐름 리팩토링 결과](LATENCY_REFACTOR_REPORT.md)
- [실행·평가 의존성 및 기반 이미지 재현성](REPRODUCIBLE_ENVIRONMENTS.md)
- [2차 최적화 구현·평가 기록](PORTFOLIO_OPTIMIZATION_REPORT.md) — 검색 병렬화, 구절 번호 인용, 중간 자료 표시, 반복 검색 캐시. 실제 일반 질문 3건 생성 성공은 단일 검증 결과이며 자연어 관련성 평가는 대기 중입니다.
- [개인 리팩토링 구현·검증 결과](PORTFOLIO_REFACTOR_REPORT.md)
- [에이전트 아키텍처 설계서](에이전트%20아키텍처%20설계서.md)
- [에이전트 시험 결과 보고서](에이전트%20시험%20결과%20보고서.md)

## AI 근거·검증 계약

- [추가 정보 요청의 유효한 보완 질문 계약](INTAKE_CLARIFICATION_CONTRACT.md)
- [사람 검색 근거 검토의 입력 계약과 지표 오염 방지](RETRIEVAL_REVIEW_CONTRACT.md)
- [사람 답변 품질 검토의 원문 근거와 출처·기존 작업 보존](HUMAN_ANSWER_REVIEW_EVIDENCE.md)
- [HTTP·SSE·저장 이력의 주장·인용 응답 계약](CITATION_RESPONSE_CONTRACT.md)
- [안전한 발췌가 있는 다음 근거 후보 선택](SAFE_CONTEXT_CANDIDATES.md)
- [MCP 검색 응답 계약과 잘못된 결과 차단](MCP_SEARCH_CONTRACT.md)
- [시연 스크립트의 인용 무결성 검증](SMOKE_CITATION_INTEGRITY.md)

## 속도·측정·출처

- [문맥 전용 DB 조회와 합성 PostgreSQL 측정](BOUNDED_CONTEXT_QUERY.md)
- [이력 목록 요약 필드 조회와 합성 PostgreSQL 측정](HISTORY_SUMMARY_PROJECTION.md)
- [검색 임베딩 클라이언트 재사용과 생성 비용 측정](EMBEDDING_CLIENT_REUSE.md)
- [키워드 조회 연결 재사용과 실제 PostgreSQL 짝 비교](KEYWORD_CONNECTION_REUSE.md)
- [벡터·키워드 후보 조회의 DB 연결 공유와 짝 비교](HYBRID_CONNECTION_REUSE.md)
- [발표 모드의 엔지니어링 측정 화면과 자료 재생성](PORTFOLIO_EVIDENCE_PANEL.md)
- [성능 측정 시점의 코드·환경·데이터 출처 계약](BENCHMARK_PROVENANCE.md)
- [벤치마크 성공 지연 통계의 표본 계약](BENCHMARK_SUCCESS_CONTRACT.md)
- [Frontend HTTP 연결 재사용·인증 격리·실측](FRONTEND_HTTP_POOL.md)
- [발표 패널의 HTTP 연결 재사용 측정 근거](HTTP_PORTFOLIO_EVIDENCE.md)
- [HTTP 측정 원본의 분야 완전성과 정수 검증](HTTP_EVIDENCE_COMPLETENESS.md)
- [시연·측정 결과 보존](MEASUREMENT_OUTPUT_PRESERVATION.md)

## 실행 상태·소유자·운영

- [실행 상태의 원자적 버전 검사와 종료 결과 보호](RUN_STATE_CONTRACT.md)
- [게스트 임시 이력의 동시 저장 유실 방지](GUEST_HISTORY_CONCURRENCY.md)
- [저장 대화 문맥 조회 단순화와 용어 대화 오류 수정](SAVED_CONTEXT_REFACTOR.md)
- [공유 Redis·모델 연결의 종료와 재사용 수명주기](SHARED_CLIENT_LIFECYCLE.md)
- [게시판·댓글·개인 이력·알림의 소유자 분리](COMMUNITY_OWNER_ISOLATION.md)
- [AI 실행·용어 결과의 회원·게스트 소유자 분리](ACTOR_RESULT_ISOLATION.md)
- [인증 갱신 응답 계약과 역할 변경 시 개인 상태 초기화](AUTH_REFRESH_CONTRACT.md)
- [로컬 메모리 세션의 조회되지 않은 만료 자료 정리](MEMORY_SESSION_EXPIRY.md)
- [운영 메트릭과 실패 로그의 상담 내용 노출 방지](SAFE_OPERATIONAL_LOGS.md)
- [분석 접수 제한과 종료 자원 정리](RUN_ADMISSION_CONTROL.md)
- [인증 비밀번호 계산의 이벤트 루프 분리](AUTH_PASSWORD_OFFLOAD.md)
- [운영·데모 인증의 공통 비밀번호 계산](DEMO_AUTH_HASHING.md)

## 화면·대화·저장

- [분석 자동 저장·완료 후 저장의 동일 실행 키](ANALYSIS_SAVE_IDEMPOTENCY.md)
- [Frontend Backend 응답 계약과 비정상 오류 본문 처리](FRONTEND_RESPONSE_CONTRACT.md)
- [SSE 상태·이벤트의 UI 반영 전 검증](SSE_PAYLOAD_CONTRACT.md)
- [Frontend HTTP 장애 안내와 분석 재시도 식별자 유지](FRONTEND_HTTP_FAILURES.md)
- [용어 답변 저장 후 후속 질문의 대화 유지](TERM_CONVERSATION_CONTINUITY.md)
- [저장 분석·용어 대화의 공통 이력 API](UNIFIED_HISTORY_API.md)
- [추가 정보 분석 실패 시 입력 보존과 성공 후 초기화](CLARIFICATION_INPUT_RECOVERY.md)
- [PDF 인용과 자료 본문의 근거 ID 연결](PDF_EVIDENCE_IDENTIFIERS.md)
- [기본 법률 용어 목록과 검색 사전의 일관성](TERM_CATALOG_CONSISTENCY.md)
- [법률 용어 목록·검색의 중첩 응답 계약](TERM_RESPONSE_CONTRACT.md)
- [분석 PDF의 세션 내 재사용과 개인 상태 정리](SESSION_PDF_REUSE.md)
- [법률 용어 대화 입력의 성공·실패 처리](TERMS_INPUT_RECOVERY.md)
- [대화 오류 후 화면 연속성](CHAT_ERROR_CONTINUITY.md)

- [용어 대화의 응답 ID와 저장 상태](TERM_REPLY_STORAGE_CONTRACT.md)

## 과거 검증 스냅샷

[PR #133 CI](https://github.com/jasnok/aio-01-p2-team2/actions/runs/36957220181)는 해당 커밋에서 481개 통과·4개 제외를 기록했다. 최신 검증은 위 CI 목록에서 커밋·상태·실제 로그를 함께 확인한다. CI 통과는 법률 정확도나 검색 관련성의 사람 평가를 의미하지 않는다.
