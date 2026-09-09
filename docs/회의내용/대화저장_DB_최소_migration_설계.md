# 대화 저장 최소 migration 검토·적용 안내

## 현재 진행 상태 (2026-09-09)

- 004_web_features.sql: 사용자 실행 완료
- 005_web_feature_indexes.sql: 사용자 실행 완료
- 006_saved_conversation_reuse.sql: 파일명 변경 완료, DB 미적용
- 현재 파일명과 통합 적용 순서를 반영한 재검증 필요

### 저장 정책

- 회원 선택 저장 대화: PostgreSQL에 자동 만료 없이 보관
- 비회원 선택 저장 대화: Redis에 7일 보관하는 방향
- 비회원 Redis 저장·TTL·인증 연결은 아직 미구현

### 기존 검증 기록 안내

아래의 2026-09-08 확인 결과와 34개 검증 통과 기록은
당시 상태에 대한 기록이다.
현재 DB 적용 상태 및 수정 후 검증 결과와 구분한다.

## 확인 결과 (2026-09-08)

- `git fetch origin develop` 후 최신 `origin/develop`: **3e0e442**, Merge PR #48. 현재 HEAD와 추적 파일 diff 없음.
- `docs/development/대화저장_후속담당_요청.md`와 `003_saved_conversations.sql`을 확인했다.
- 실제 DB는 `database/.env`와 `legal_mcp/.env`가 지정하는 동일 연결을 읽기 전용·repeatable read 트랜잭션으로 조사했다. PostgreSQL **16.15**, DB `legal_ai`. 연결 문자열·비밀번호·사용자 데이터는 출력하지 않았다.
- 실제 `public.users / saved_conversations / saved_messages / saved_message_sources` 컬럼, PK, UNIQUE, FK, 인덱스는 조사 시점의 003과 일치했다. 네 테이블 각각 **0행**. 이는 조사 시점의 관측값이며 적용 시 재확인이 필요하다.
- 실제 DB에는 로컬 미추적 `004_web_features.sql`의 users 확장이 없었다. 이 파일은 수정·적용하지 않았다. 005는 003에 직접 적용 가능하며 004에 의존하지 않는다. 파일 번호 004가 건너뛰어졌다고 일괄 실행하지 않는다.
- Backend `.env`에는 DATABASE_URL이 없었다. `backend/app/core/config.py`의 기본 URL을 사용하는 구성이다. Backend 프로세스 환경변수와 실운영 연결은 이번 조사로 확정되지 않았으므로 연결 대상 통일은 배포 전 필수 확인사항이다.

## 실제 스키마와 005의 차이

| 대상                  | 실제 현재                                               | 변경                                                                    |
| --------------------- | ------------------------------------------------------- | ----------------------------------------------------------------------- |
| users                 | bigint id, 필수·고유 anonymous_key, 생성/수정 시각      | nullable actor_issuer/actor_subject, 두 값 동시 존재 CHECK, 복합 UNIQUE |
| saved_conversations   | user FK, title, 전역 UNIQUE source_request_id, 시각     | category, save_state, saved_at, expires_at 및 CHECK                     |
| saved_messages        | conversation FK CASCADE, role, content, bigint id, 시각 | execution_key, processing_status, JSONB snapshot 및 CHECK/UNIQUE        |
| saved_message_sources | message FK CASCADE, document/chunk FK NO ACTION, URL    | UNIQUE NULLS NOT DISTINCT에 source_url 추가; 기존 행/FK 유지            |
| 조회 인덱스           | PK/UNIQUE 인덱스만 존재                                 | 사용자별 이력, 대화별 최신 메시지, 완료 assistant, 최초 user 인덱스     |

기존 테이블/행 삭제·초기화, 기존 내용 UPDATE, 추정 소유권/상태 backfill은 없다. 기존 메시지 순서는 이미 존재하는 BIGSERIAL `id`로 표현한다. 별도 sequence 컬럼, 대화 벡터 검색, 실행 로그 테이블은 추가하지 않는다.

## 인증 Actor → users 매핑

현재 `mock_store.py`의 Actor는 `user-demo`, `admin-demo`, UUID 문자열 계정과 메모리 세션을 사용한다. 토큰 없는 요청은 전달된 `X-Guest-ID` 또는 공용 `guest-anonymous`가 된다. 이 값은 검증된 비회원 자격증명이 아니다. `routers/legal.py`의 동기 분석은 Actor 의존성 없이 `x_guest_id or request.session_id`로 구분한다. `agent_run_service.py`도 MemoryStore를 쓴다. DB의 bigint user ID로 캐스팅하거나 같은 문자열이라는 이유로 익명 데이터를 귀속시키면 안 된다.

운영 Repository의 사전 조건:

1. 동기/SSE 모두 동일한 인증 의존성으로 서버가 검증한 지속성 있는 `(issuer, subject)`를 얻는다. issuer는 서버 허용 목록에서 결정하고 subject는 검증된 세션/인증 제공자로부터 얻는다. mock Actor·헤더·요청 body로 이 값을 만들지 않는다.
2. `users WHERE actor_issuer=$1 AND actor_subject=$2`의 bigint id로 소유권을 확인한다. 매핑 없는 계정은 신뢰할 수 있는 계정 생성 경로에서만 등록한다. 매핑 변경은 본인 확인을 거친 별도 계정 연결 절차이며 이메일 일치만으로 연결하지 않는다.
3. 003의 필수 anonymous_key를 유지한다. 003 기반 신규 회원 행에는 서버 생성 무작위 opaque 키(100자 이내)를 호환값으로 넣는다. 이 키를 로그인 수단으로 쓰지 않는다. 004가 적용된 경우에는 회원 생성 코드가 해당 role/email/password_hash/display_name 제약도 충족해야 한다. 005가 회원을 GUEST로 등록하는 기능은 없다.
4. 동시 가입은 `(actor_issuer,actor_subject)` UNIQUE로 직렬화한다. `INSERT ... ON CONFLICT (actor_issuer,actor_subject) DO NOTHING` 후 같은 검증된 쌍으로 조회한다. arbitrary user_id에 `UPDATE ... SET actor_subject`하는 upsert는 금지한다.
5. 기존 행에는 두 필드 모두 NULL이다. 자동 매핑하지 않는다. 접근하려면 별도 소유권 입증이 필요하며, 그 전에는 보존하되 신규 인증 경로에 노출하지 않는다. 관리자 role만으로 다른 사용자의 대화 접근을 허용하지 않는다.

이 migration은 안전한 매핑을 **지원하는 스키마**를 제공한다. 지속성 있는 인증·계정 연결과 Repository가 구현되기 전까지 운영 대화 저장 활성화는 보류한다. DB 역할에 모든 행 권한이 있으므로 SQL 예시의 소유권 조건을 생략할 수 없고, DB 제약 자체가 HTTP 인증을 대신하지 않는다.

## 저장·만료·처리 상태

- 저장 버튼/명시적 선택이 있는 결과만 쓰는 것을 기본 계약으로 한다. 선택하지 않은 대화는 기존 임시 실행 저장소에만 있으며 `saved_conversations`에 draft 행을 만들지 않는다. 이후 턴까지 저장할지 선택 범위를 UI/정책으로 확정하고 각 쓰기에서 확인한다.
- 신규 저장: `save_state='selected'`, category와 실제 선택 시각 saved_at 필수. category는 housing/labor/consumer. 변경 시 기존 대화의 분야와 맞는지 Service가 검사한다.
- 기존 행/003 방식의 쓰기는 `legacy`, saved_at/category/snapshot은 NULL 허용. 기존 동의를 새로 입증한 것으로 표시하지 않는다. 이 기본값은 구버전 SQL 호환용이며 신규 Repository는 legacy를 쓰지 않는다.
- expires_at은 향후 보관 정책을 위한 nullable 필드다. 기존 행에는 만료를 소급하지 않는다. 현재 자동 만료 작업·비회원 인증·7일 동의 정책은 **미구현**이며 비회원 저장도 활성화하지 않는다. 회원 선택 저장도 안내한 보관·삭제 정책 안에서만 수행한다.
- 메시지는 선택된 최종 결과만 저장한다. `completed/failed/stopped`를 구분하며 queued/running/내부 tool timeline은 기존 실행 저장소에 둔다. 실패 결과도 사용자 선택과 안전한 오류 표현이 있을 때만 저장한다. 최초 실패를 성공으로 덮어쓰지 않고 명시적 재실행은 새 실행 키를 쓴다.
- 과거 메시지의 상태를 완료로 추정하지 않는다. legacy는 이력 복원에서 content로 보여 줄 수 있지만 완료 턴 Context에는 자동 포함하지 않는다. 최초 user 질문만 별도로 참조한다.

## 실행 중복·순서·트랜잭션

`execution_key`는 서버 생성 전역 고유 실행 ID를 200자 이내로 정규화한다. 예: `lawpath:run:<uuid>` 또는 `lawpath:request:<uuid>`. SSE run과 내부 response.request_id가 다르므로 공통 저장 함수가 **하나의 canonical 실행 키**를 받아야 한다. 같은 실행의 동기/완료 콜백/재시도는 같은 키, 새 분석은 새 키다. 클라이언트 Idempotency-Key나 `req-<session>` 같은 mock 키를 그대로 사용하지 않는다.

`UNIQUE(execution_key, role)`은 한 실행의 user와 assistant를 각각 한 번만 저장하고 **다른 conversation으로 재저장하는 경우도 차단**한다. legacy의 NULL 실행 키는 PostgreSQL 기본 NULL-distinct 동작으로 여러 행을 허용한다. 사용자/assistant 쌍이 반드시 함께 존재한다는 것은 UNIQUE만으로 보장되지 않는다. Repository가 아래 트랜잭션을 지켜야 한다.

1. 인증·명시적 저장 선택·category·실행 소유권을 확인하고 기존 pool에서 transaction 시작.
2. 신규 대화는 최초 canonical 실행 ID를 source_request_id(100자 이내)에 넣는다. 이 값은 후속 턴에서 바꾸지 않는다. 기존 UNIQUE가 최초 실행에 대한 대화 중복 생성도 막는다. 충돌 시 소유권 확인 없는 기존 대화 반환 금지.
3. `saved_lock`으로 대화 행 잠금 및 소유권/만료 재검증. 이 잠금 안에서 중복 키 조회 → 입력 질문과 기존 snapshot 비교. 동일 재전송은 기존 결과 반환, 다른 입력·다른 대화면 conflict. 전역 키 충돌만으로 다른 사용자의 결과를 조회/반환하지 않는다.
4. user 먼저, assistant 다음 순서로 INSERT. 둘 다 같은 execution_key/최종 상태. 기존 bigint id가 저장 순서를 결정한다. 시퀀스 gap은 정상이며 연속 숫자나 created_at 동률에 의존하지 않는다. 대화 내 병렬 분석을 허용하면 저장 완료 순서가 대화 순서가 되므로, 제출 순서가 필요해질 때만 별도 turn 번호를 도입한다.
5. snapshot 및 sources 연결 저장, `saved_conversations.updated_at=now()` 갱신 후 COMMIT. 중간 오류는 두 메시지·근거 링크 모두 rollback. 성공 COMMIT 전에 저장 완료 SSE를 보내지 않는다.

일반 실패 복구는 동일 키 재시도로 처리한다. `ON CONFLICT DO UPDATE content=...`로 이전 결과를 조용히 덮어쓰지 않는다. 전체 E2E 및 다중 연결 동시성은 후속 Repository 구현 시 검증해야 한다.

## 복원 snapshot과 원본 출처

`snapshot = {"version":1,"payload":{...}}`로 버전을 둔다. user payload는 입력 LegalQuestionRequest의 필요한 필드(question/category 및 사용자 보완정보), assistant payload는 `LegalQuestionResponse.model_dump(mode='json')` 결과를 저장한다. request_id, agent_id, status, termination_reason, question_summary, key_issues, answer, related_laws, similar_cases, consultations, sources, follow_up_questions, cautions, is_mock가 복원 대상이다. SSE run_id는 payload의 추가 필드 또는 실행 키 대응으로 보관한다.

CHECK는 버전과 JSON object 외형만 검사한다. 전체 응답 모델·role별 payload 적합성·크기 상한(예: 메시지당 직렬화 256 KiB)은 Service가 검증한다. 세션 토큰/비밀번호/원시 오류는 저장하지 않는다. legacy에 없는 JSON을 사후에 완전 복원했다고 주장하지 않는다.

기존 `saved_message_sources`를 그대로 재사용한다. API Evidence의 문자열 ID를 bigint로 임의 캐스팅하지 말고 MCP가 검증한 실제 document/chunk PK로 매핑한다. 없는 PK를 만들지 않는다. URL만 있는 외부 출처는 두 FK를 NULL로 저장할 수 있다. 기존 UNIQUE는 `(message_id,NULL,NULL)`을 한 개만 허용해 서로 다른 외부 URL을 잃을 수 있으므로, **source_url을 UNIQUE에 추가**한다. 완전히 같은 링크만 중복 차단하고 기존 행은 모두 유지한다. source_id/evidence_id/title 등 API 복원 정보는 snapshot에도 유지한다.

Frontend 출처 버튼/기관 메타 제거는 출력 정책일 뿐이다. snapshot·sources 원본을 삭제하거나 비우지 않는다. 사용자 표현에는 기존 Frontend 표시 계약을 계속 적용한다. 대화 내용을 법률 근거로 신뢰하지 않고 후속 분석 시 MCP 재검색한다.

## 조회와 인덱스

실행 가능한 bind SQL은 `database/scripts/saved_conversation_queries.sql`에 있다. PREPARE는 예시용이며 asyncpg에서는 본문 SELECT/DELETE를 `$1...` 인자와 함께 호출하면 된다.

| 인덱스/제약                                                              | 용도                                                         |
| ------------------------------------------------------------------------ | ------------------------------------------------------------ |
| users_actor_identity_key                                                 | 검증된 issuer/subject → users.id                             |
| saved_conversations_owner_latest_idx (user_id, updated_at DESC, id DESC) | 소유자 이력 페이지, 사용자 FK 조회                           |
| saved_messages_conversation_latest_idx (conversation_id, id DESC)        | 최신 메시지, 상세 keyset 페이지, 부모 삭제 자식 탐색         |
| saved_messages_completed_turn_idx                                        | completed assistant 최신 3개 후보; 실패/legacy 제외          |
| saved_messages_first_question_idx                                        | 최초 user 1개를 대화 길이에 무관하게 인덱스 탐색             |
| saved_messages_execution_role_key                                        | 전역 실행별 역할 중복 차단, 완료 턴의 user/assistant 짝 조회 |
| saved_message_sources_reference_key                                      | message별 근거 조회와 동일 URL/PK 연결 중복 차단             |

`saved_context`는 최초 질문 + 최근 완료 **3쌍**을 UNION하여 최대 7행을 반환한다. 최근 2턴이 필요하면 LIMIT 3을 2로 바꾼다. 전체 대화를 읽어 Python에서 자르지 않는다. 직전 답변의 follow_up_questions와 근거 연결 ID도 반환한다. 예시는 content 4,000자/행, 근거 20개/행으로 제한하며 Service에서 보완 질문 수/길이와 합계 토큰 상한(예: 8,000 tokens)을 추가 적용한다. 전체 snapshot은 Context에 보내지 않는다. 선택된 근거 ID 상세조회에도 동일 소유권/만료 검사를 적용한다.

`saved_restore`는 최대 50행씩 id keyset으로 원래 JSON을 복원한다. 저장 상태/category는 saved_owner에서 얻는다. expired는 조회하지 않되 명시적 소유자 삭제는 가능하다. 기존 /history API 및 SSE 계약 변경은 이 SQL 작업에 포함되지 않는다.

## 삭제·만료

명시적 대화 삭제 SQL에 Actor 조건을 포함했다. conversation 삭제 → messages CASCADE → source 연결 CASCADE. legal_documents/legal_chunks는 삭제하지 않는다. 반대로 링크가 참조하는 원본 문서를 지우면 기존 FK NO ACTION이 막으므로 수집 파이프라인이 원본을 임의 삭제하는 것도 주의한다. users 삭제는 기존 conversation FK NO ACTION을 유지하며 계정 탈퇴 정책에 따른 별도 트랜잭션이 필요하다.

7일 보관은 이번에 완료하지 않았다. 추후 비회원 저장 활성화 조건은 서버 검증 guest 세션, 동의·기산점·재접속 정책, expires_at 설정, 모든 읽기/쓰기의 만료 필터, 자동 배치 삭제, 실패 재시도/관측/알림, 백업 보관 정책, 실제 스케줄러 및 E2E 검증이다. future worker는 만료 대화 배치를 `FOR UPDATE SKIP LOCKED`로 잠근 뒤 부모 행을 삭제해 같은 CASCADE를 사용한다. 그때 expires_at partial index도 추가한다. 지금은 만료 worker나 스케줄러를 만들거나 실행하지 않았다.

## 검증 결과

- 공유 DB: 스키마·제약·인덱스·count **읽기만 수행**, migration 적용 안 함.
- 격리된 메모리 PGlite **0.5.8 / PostgreSQL 18.3**에서 `database/tests/test_saved_conversation_migration.mjs` 실행. 원본 문서/청크는 FK 테스트용 PK stub이며 벡터 확장에는 의존하지 않는다.
- 기존 데이터/출처 보존, 구버전 INSERT, 추정 매핑 방지, 중복 Actor/실행·다른 대화 재저장, JSON 필수 키와 null 거부, 최초 질문+3턴, 타인 조회/복원/삭제 차단, 만료 조회 차단, CASCADE와 원본 보존, schema drift 거부, 재적용 실패, 후반 SQL 오류 전체 rollback 검증.
- 최종 실행 결과: **34개 assertion 통과**, 프로세스 종료 코드 0.
- 로컬 미추적 004 다음 005 적용 호환성도 검증한다(004가 없는 checkout에서는 이 항목만 명시적으로 SKIP).
- 실제 서버와 메이저 버전이 다르므로 **PostgreSQL 16 복원본 staging 검증은 미완료**. 대용량 실행 계획/잠금 시간, 다중 연결 경쟁, Backend 인증 통합/재시작 복원, 동기/SSE E2E도 아직 검증하지 않았다. SQL 예시 검증이 Repository 구현 완료를 의미하지 않는다.

재현: Node 환경에 `@electric-sql/pglite@0.5.8` 설치 후

```text
node database/tests/test_saved_conversation_migration.mjs <PGlite 설치 디렉터리의 dist/index.js 절대경로>
```

DB 점검 재현: 프로젝트 Python에 database/requirements.txt의 psycopg/python-dotenv 준비 후 `python database/scripts/inspect_saved_conversations.py`. 이 스크립트는 연결의 default_transaction_read_only 및 statement_timeout을 강제한다.

## 승인 후 적용 순서·복구

1. 담당자 승인, 정확한 DB host/database/role·Backend process 설정, 실제 카탈로그 및 행 수 재확인. 004 포함 자동 glob migration 실행 금지. 005는 1회 적용 파일이다. 이미 적용되었거나 컬럼/제약이 다르면 중단하여 이력을 확인한다.
2. 네 테이블 및 의존 법률 데이터/시퀀스를 포함한 일관된 백업을 만들고 **별도 DB 복원 시험**. 기존 내용·근거 row count와 FK, 사용 가능한 디스크를 기록한다. 공유 DB에 백업 복원을 덮어쓰지 않는다.
3. 동일 PostgreSQL 16 staging 복원본에서 005와 Repository 쿼리/권한/실패 복구 테스트. 004는 승인된 별도 변경인 경우에만 적용한다. 선택 저장/인증 통합이 없는 상태에서 기능을 켜지 않는다.
4. 짧은 점검 시간에 관련 쓰기를 멈추고 `psql -X -v ON_ERROR_STOP=1 -f database/migrations/005_saved_conversation_reuse.sql` 실행. 접속 정보는 안전한 서비스/환경 설정으로 전달한다. SQL은 BEGIN/COMMIT, lock_timeout 5초, statement_timeout 60초 및 카탈로그 guard를 포함한다. 전체 테이블 lock을 쓰므로 데이터가 커졌다면 온라인 인덱스 구축을 별도 승인 설계로 분리한다.
5. 적용 후 행/원본 내용이 보존되었는지, 추가 CHECK/UNIQUE가 validated인지, 인덱스 valid인지 재검사하고 ANALYZE를 수행한다. migration 이력에 파일 checksum/시각/적용자를 기록한다. Source upsert가 기존 제약 이름이나 3열 conflict target을 쓰면 4열 target으로 함께 갱신해야 한다.
6. Repository/공통 저장 경로·안전한 인증 준비 후 선택 저장을 단계적으로 활성화하고 동기/SSE 중복 완료 및 재시작 복원을 점검한다.

**실행 도중 실패:** ON_ERROR_STOP으로 종료하고 연결 종료 또는 ROLLBACK. PostgreSQL transactional DDL이 필드·인덱스·출처 제약 변경을 모두 되돌린다. 원인을 해결하고 실제 상태를 재점검한 후 다시 실행한다. 재실행 시 IF NOT EXISTS로 불일치를 숨기지 않는다.

**COMMIT 후 문제:** 우선 새 저장을 비활성화하고 애플리케이션을 되돌리되 확장 스키마·데이터는 유지한다. 구버전 source upsert의 conflict target은 새 제약과 호환되지 않으므로 해당 쓰기도 차단한다. 이것이 기본적인 무손실 복구다. 컬럼 DROP/테이블 삭제를 자동 down으로 제공하지 않는다.

물리적 schema rollback이 꼭 필요하면 별도 승인·백업·신규 snapshot/Actor 데이터 export를 먼저 한다. 특히 새 source UNIQUE 아래서는 같은 message/document/chunk에 URL이 다른 행이 존재할 수 있어 이전 UNIQUE를 그대로 복원할 수 없다. `GROUP BY message_id,document_id,chunk_id HAVING count(*)>1`을 점검하고 **충돌 행을 삭제해 맞추지 않는다**. 충돌이 있으면 확장 제약 유지와 forward fix를 선택한다. 백업은 별도 DB로 복원한 뒤 누락 데이터를 대조·복구하며 공유 DB 전체를 과거 시점으로 덮어쓰지 않는다.
