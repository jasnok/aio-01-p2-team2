# 생활 법률 RAG 데이터베이스

주택임대차·노동·소비자 분야의 법률 검색을 지원하는 PostgreSQL·pgvector 데이터 계층입니다. 파일과 공식 API로 확보한 자료를 정규화하고 검색용 청크와 임베딩을 저장합니다. 일반 웹 기능용 DB 스키마도 관리합니다.

실제 실행 명령과 옵션은 [스크립트 사용 안내](scripts/README.md)를 참고합니다.

## 1. 담당 범위와 연결 구조

```text
Frontend → Backend
              ├─ 일반 웹 기능 → PostgreSQL
              ├─ 법률 검색 → Legal MCP → PostgreSQL + pgvector
              └─ 대화·Session·실행 상태 → Redis
                             Legal MCP → Redis 검색 Cache
```

Frontend는 Backend만 호출하며 DB에 직접 접근하지 않습니다.

| 영역 | DB 담당 역할 | 연동 담당 역할 |
|---|---|---|
| PostgreSQL | 스키마·제약·인덱스·권한·Migration·데이터 관리 | Backend가 웹 기능 CRUD 구현 |
| RAG | 원본·출처·정규화·청크·임베딩·적재 검증 | MCP가 검색·순위·근거 반환 구현 |
| Redis | 서버·인증·접속정보·정책·동작 검증 지원 | Backend가 대화·Session·상태 저장 |
| 검색 Cache | TTL·무효화·장애 정책 협의 | MCP가 조회·저장·우회 구현 |

**Supabase 백업·Fallback은 팀 합의로 이번 MVP 범위에서 제외합니다.** Docker PostgreSQL을 단일 운영 DB로 사용하며 영속 볼륨 보존과 Migration 전 로컬 백업은 별도로 관리합니다.

## 2. 기술 구성

| 구성 요소 | 사용 기술 |
|---|---|
| 관계형 DB·벡터 검색 | PostgreSQL 16, pgvector |
| 임베딩 | OpenAI `text-embedding-3-small`, 1536차원 |
| 임시 저장·Cache | Redis 7 |
| 데이터 처리 | Python, Pydantic, psycopg |
| PDF 추출 | pdfplumber |
| 실행 환경 | Docker Compose, Python 가상환경 |

pdfplumber는 PDF 본문 추출 도구이며 벡터 생성은 OpenAI 임베딩 모델이 담당합니다.

## 3. 수집·사용 원칙

```text
파일 우선 → 부족한 공식 본문 API 사전 수집
→ 정규화·청크·임베딩·DB 저장 → 사용자 질문 시 내부 DB 검색
```

외부 법률 API는 사전 수집·갱신에 사용합니다. 질문마다 법률 원문을 수집·적재하지 않습니다. 질문을 검색 벡터로 변환할 때는 임베딩 API를 호출할 수 있습니다.

| 유형 | 자료 | 사용 기준 |
|---|---|---|
| `LAW` | 국가법령정보센터 법령 본문 | 조문 검색·답변 근거 |
| `CASE` | 공식 API 판례·확보한 판결문 PDF | 유사 판례·판단 근거 |
| `CONSULTATION` | 한국소비자원 피해구제 사례 | 상담·분쟁 사례 참고 |
| `ADMIN_DECISION` | 노동위원회 판정자료 | 본문 보유 여부에 따라 사용 |
| 보조 자료 | 일상용어·법령 색인 | 용어 설명·수집 대상 식별 |

- 소비자 사례와 노동위원회 자료는 법원 판례와 구분합니다.
- 상세 판정문 없는 노동 CSV는 색인으로 활용하고 답변 근거 사용을 제한합니다.
- 과거 법령 색인을 현행 조문 근거로 사용하지 않습니다.
- PDF 제공 서비스와 판결 법원은 별도로 관리합니다. URL 존재와 공식성·최신성 검증도 별개입니다.
- 근거가 부족하면 근거 부족으로 처리하고 후속 수집 대상으로 관리합니다.

## 4. 적재 현황

**2026-09-09 점검 시점의 DB 스냅샷입니다.** 이후 추가 원본·적재 결과를 자동 반영한 수치가 아닙니다. 원본 파일 수와 DB 적재 수는 다를 수 있습니다.

| 카테고리 | 법령 | API 판례 | PDF 판례 | 기타 |
|---|---:|---:|---:|---|
| Housing | 3 | 6 | 10 | — |
| Labor | 2 | 5 | 8 | 노동 판정자료 399건 |
| Consumer | 3 | 5 | 8 | 소비자 피해구제 678건 |

민법은 기본 category가 housing이며 `metadata.categories`에 consumer도 등록되어 있습니다. 법령 수는 기본 category 기준입니다.

```text
문서: 1,127건
청크·임베딩: 각각 3,310건
모델: text-embedding-3-small
차원: 전부 1536
```

점검 당시 PDF 26건은 현재 추출 결과의 본문·청크 해시와 DB 값이 일치했습니다. 저장 상태와 검색 정확도·표 추출 품질은 별도 검증 대상입니다.

## 5. 디렉터리 구조

```text
database/
├─ README.md                 # 전체 운영 안내
├─ .env.example              # 설정 예시
├─ requirements.txt          # 의존성
├─ migrations/               # 스키마·인덱스 SQL
├─ ingestion/
│  ├─ collectors/            # API 수집
│  ├─ normalizers/           # XML·PDF·CSV 정규화
│  ├─ chunkers/              # 청크 생성
│  ├─ embedders/             # 임베딩 호출
│  ├─ models.py              # 공통 모델
│  └─ text_quality.py        # 품질 검사
├─ raw/
│  ├─ api/laws/              # 법령 XML
│  ├─ api/cases/             # 카테고리별 판례 XML
│  └─ files/                 # 분야별 PDF·CSV·소비자 XML·보조 자료
├─ scripts/                  # 실행 파일·검증 SQL
├─ seeds/                    # 초기·고정 검증 데이터 안내
├─ sources/                  # 출처 관리용
├─ normalized/               # 중간 산출물 보관용
├─ repositories/             # DB 접근 공통화용
└─ tests/                    # DB 관련 테스트
```

일부 디렉터리는 확장용입니다. 공통 Python 모델을 사용하는 현재 파이프라인에서는 JSONL 중간 파일이 필수가 아닙니다. 법률 원본은 raw에 유지하고 초기 계정·FAQ와 혼합하지 않습니다.

## 6. 주요 테이블

| 테이블 | 용도 |
|---|---|
| `legal_documents` | 본문·유형·출처·메타데이터 |
| `legal_chunks` | 검색 청크·해시·임베딩 |
| `ingestion_runs` | 적재 실행 이력 |
| `users` | 회원·관리자·기존 익명 사용자 식별 |
| `faqs` | 공지·안내 FAQ |
| `questions`, `question_comments` | 질문·댓글 |
| `notifications`, `query_history` | 알림·질문 및 분석 이력 |
| `audit_logs` | 관리자 주요 행위 |
| `saved_conversations`, `saved_messages` | 명시적으로 저장한 대화·메시지 |
| `saved_message_sources` | 저장 답변 출처 |

문서는 `UNIQUE(source_name, external_id)`, 청크는 `UNIQUE(document_id, chunk_index)`로 중복을 방지합니다. 소유자 제약은 구조를 검증하며 실제 사용자 접근 권한은 Backend가 검사합니다.

## 7. 환경설정·Docker

Python 준비는 [scripts/README.md](scripts/README.md)를 참고합니다. 적재·검색의 모델·차원을 동일하게 설정하고 비밀값은 Git에 올리지 않습니다.

현재 실제 Compose 파일은 루트의 `docker-compose.yml`입니다. 프로젝트 루트에서 실행합니다.

```powershell
docker compose --env-file .env -f docker-compose.yml up -d
```

- 루트 `.env`: Compose용 `POSTGRES_PASSWORD`, `REDIS_PASSWORD` 등 설정.
- `database/.env`: Python 수집·적재·검색 설정.
- 기존 동일 이름 컨테이너가 있으면 관리 방식과 상태를 먼저 확인합니다.
- PostgreSQL은 영속 볼륨을 사용합니다. 초기화 SQL은 빈 데이터 디렉터리 최초 생성 시에만 실행됩니다.
- 기존 볼륨에 후속 Migration은 자동 적용되지 않습니다.
- 문서의 `docker-compose_v2.yml` 명칭은 실제 파일명과 통일이 필요합니다.

## 8. Migration 관리

| 파일 | 역할 |
|---|---|
| `001_init.sql` | 법률 문서·청크·적재 이력 |
| `002_search_indexes.sql` | 법률 검색 인덱스 |
| `003_saved_conversations.sql` | 사용자·저장 대화 기본 구조 |
| `004_web_features.sql` | 회원 확장·일반 웹 기능 |
| `005_web_feature_indexes.sql` | 웹 조회 인덱스 |
| `006_saved_conversation_reuse.sql` | 대화·메시지·출처 확장 |

점검 당시 주요 구조가 DB에 존재했습니다. 적용 이력과 통합 실행기는 후속 작업입니다. **006은 재실행 시 실패하도록 작성되어 있으므로 전체 SQL을 무조건 재실행하지 않습니다.**

```text
현재 스키마·적용 여부 확인 → 변경 검토·로컬 백업
→ 미적용 SQL 실행 → 스키마·기능 검증
```

## 9. 적재·검색 검증

판례는 품질검사 → 대상 확인 → 적재·임베딩 → 완료 확인 순서입니다. `--only-new`는 현재 판례에서 신규·본문 변경·임베딩 미완료를 선별하며 모델·청크 정책 변경까지 모두 감지하지는 않습니다.

```sql
SELECT
    d.category, d.document_type,
    COUNT(DISTINCT d.id) AS document_count,
    COUNT(DISTINCT d.id) FILTER (WHERE c.id IS NULL)
        AS documents_without_chunks,
    COUNT(c.id) AS chunk_count,
    COUNT(c.embedding) AS embedding_count,
    COUNT(c.id) - COUNT(c.embedding) AS missing_embeddings,
    MIN(vector_dims(c.embedding)) AS min_dimension,
    MAX(vector_dims(c.embedding)) AS max_dimension
FROM legal_documents d
LEFT JOIN legal_chunks c ON c.document_id = d.id
GROUP BY d.category, d.document_type
ORDER BY d.category, d.document_type;
```

근거용 문서는 청크·출처·해시가 존재하고 벡터 누락이 없어야 합니다. 색인 자료는 별도 기준으로 해석합니다.

검색 평가는 분야별 5문항, 총 15문항 중 최소 12문항에서 기대 문서가 Top 3에 포함되는 것을 목표로 합니다. 필터·중복·낮은 관련성·출처·근거 부족 처리도 확인합니다. 로컬 검색과 실제 MCP 서비스는 별도 검증합니다.

## 10. Redis·웹 데이터 정책

| 데이터 | 정책 | 구현 담당 |
|---|---|---|
| 최근 대화 | TTL 604800초, 최대 20개 메시지 | Backend |
| 검색 Cache | 권장 TTL 600초, 세부 계약 확정 필요 | MCP |
| Agent 상태 | 권장 TTL 1800초, 세부 계약 확정 필요 | Backend |
| 로그인 Session | 인증 정책으로 별도 확정 | Backend |

20개는 메시지 단위로 질문·답변을 각각 저장하면 약 10회 문답입니다. TTL 갱신 시점도 명시해야 합니다. 법률 원문·임베딩을 Redis에 사전 복제하지 않습니다.

검증 순서는 연결 → 21개 입력 → 길이 20·TTL 확인 → Cache miss/hit → Redis 장애 시 DB 검색 유지입니다. 재적재·검색 설정 변경 후 Cache 무효화가 필요합니다.

웹 데이터는 Backend가 PostgreSQL에 직접 저장합니다. 비밀번호는 해시만 저장하고 비회원 7일 보관은 만료 시각 설정·조회 제외·정리 절차로 구현합니다. 이력과 명시적 저장 대화는 구분하며 CRUD·권한·재시작 후 유지까지 검증합니다.

## 11. 완료 상태·후속 작업

점검 시점 기준이며 다른 PC의 최신 배포 상태는 통합 테스트로 확인합니다.

| 항목 | 상태 |
|---|---|
| 핵심 법령·API/PDF 판례·소비자 사례 적재 | 확인 완료 |
| 점검 PDF 26건 해시·전체 임베딩 모델·차원 | 확인 완료 |
| 일반 웹 테이블·주요 제약·인덱스 | 확인 완료 |
| Migration 이력·실행기·통합 DB 검사 | 보완 필요 |
| `ingestion_runs` 기록·노동 자료 근거 사용 제한 | 보완 필요 |
| MCP Hybrid Search·15문항 평가 | 보완·검증 필요 |
| Backend 영구저장·전체 E2E | 통합 검증 필요 |
| Redis 대화·Cache·장애 대응 | 구현·검증 필요 |
| Supabase 백업·Fallback | 범위 제외 |

인수인계에는 접속·권한 계약, 스키마·Migration 절차, 자료 출처·사용 범위, 재현 가능한 명령, 적재·검색·CRUD·Redis 검증 결과를 포함합니다.
