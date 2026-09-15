# LawPath 생활 법률 검색 AI Agent

사용자가 생활 법률 상황을 입력하면 Backend Agent가 MCP 검색 도구를 통해 법령·상담사례·판례를 검색하고, 출처와 함께 Frontend에 표시하는 팀 프로젝트입니다.

지원 분야는 임대차·주거(`housing`), 근로·임금(`labor`), 소비자·중고거래(`consumer`)입니다. 상담사례(`CONSULTATION`)와 법원 판례(`CASE`)는 서로 다른 자료로 구분합니다.

## 첫 통합 목표

소비자·중고거래에서 다음 질문을 입력합니다.

> 신용카드 일시불 결제 후 할부로 전환했는데 물건이 배송되지 않았습니다. 카드사에 할부항변권을 행사할 수 있나요?

목표 경로:

```text
Frontend 내 사례 분석
→ Backend Consumer Agent
→ MCP: search_laws / search_consultations / search_cases (각 top_k=3)
→ PostgreSQL + pgvector
→ MCP: 법령 3건 / 상담사례 3건 / 판례 3건
→ Backend: related_laws / consultations / similar_cases
→ Frontend: 유형별 3건, 총 9건과 출처 표시
```

완료 기준:

- MCP 결과, Backend JSON, Frontend 카드의 유형별 건수와 문서 ID가 일치한다.
- 상담사례와 판례를 혼합하지 않고 각각 표시한다.
- 제목·본문 또는 요약·출처 URL이 전달되고, 문서 내용이 질문과 관련 있는지 확인한다.
- 자료가 부족하면 실제 검색된 건수만 반환한다. 중복·무관한 자료나 생성한 근거로 9건을 채우지 않는다.
- 검색하지 않음, 검색 결과 없음, 검색 실패, 추가 정보 필요를 구분한다.
- HTTP 200이나 총 9건 반환만으로 법률 답변의 정확성 또는 화면까지의 통합 완료를 판정하지 않는다.

현재 검색은 문서 ID 기준 중복 제거를 사용합니다. 법령 3건을 서로 다른 법령 문서로 셀지, 같은 법령의 서로 다른 조문도 포함할지는 담당 간 계약을 확정해야 합니다.

## 현재 확인 상태 — 2026-09-08

원격 develop `d14f595` 코드와 팀 실행 서버를 따로 확인했습니다. 실행 서버에는 원격 develop에 아직 없는 추가정보 확인 동작 등이 있으므로, 서버 동작을 해당 커밋의 구현으로 간주하지 않습니다.

| 항목 | 확인 결과 |
|---|---|
| MCP 소비자 개별 검색 | 동일 대표 질문으로 법령·상담사례·판례 각각 3건 반환 확인 |
| Backend 소비자 내 사례 분석 | 이번 재검증에서 `related_laws=3`, `consultations=3`, `similar_cases=3` 반환 확인 |
| Frontend 총 9건 표시 | 이번 검증은 API 호출 기준이며 실제 화면의 최종 표시 확인은 남아 있음 |
| 임대차·근로 대표 질문 | `status=stopped`, `termination_reason=needs_clarification` 및 추가 질문 반환 |
| 임대차·근로 정보 보완 질문 | 두 분야 모두 법령 1건·판례 2건·상담사례 0건 반환 확인 |
| MCP 임대차·근로 상담사례 직접 검색 | 각 대표 질문으로 정상 응답의 빈 배열 반환. DB 미적재로 단정하지 말고 적재·필터·임베딩 확인 필요 |
| 별도 법/판례 검색 화면 | 원격 develop의 GET API는 MCP 호출 없이 빈 배열을 반환하는 임시 구현 |
| 회원·FAQ·알림·이력 | API 경로가 있어도 원격 develop에는 Backend 메모리 저장소 의존성이 남아 있음 |

검증용 요청 ID:

- 소비자 9건: `req-98d354de-1234-45e9-a29b-798736764b0b`
- 임대차 정보 보완 후 검색: `req-14e1990f-bb20-446c-ac05-ee23d049cfe7`
- 근로 근무기간 명시 후 검색: `req-c82ebf8a-4a00-4828-8866-c07a1b04d947`

원격 develop의 Runtime은 전체 근거 3건에서 후속 Tool을 중단하고, 임대차·근로 Profile은 상담사례 Tool을 허용하지 않습니다. 실행 서버의 개선 코드를 push하고 PR로 공유한 뒤 이 차이를 해소해야 합니다.

## 구조와 책임

```text
Frontend (Streamlit)
  → Backend (FastAPI + 공통 AgentRuntime + 분야별 Profile)
    → Legal MCP (Tool → Search Service → Repository)
      → PostgreSQL + pgvector: 법률 자료 검색

Backend → PostgreSQL: 회원·FAQ·질의 이력·알림 등 일반 서비스 데이터 (전환 대상)
database/: 외부 API·원문 사전 수집 → 정규화 → Chunk → Embedding
```

사용자 질문은 내부 DB 검색을 기본으로 합니다. Frontend는 Backend API만 호출하고 DB나 MCP에 직접 연결하지 않습니다. 법률 검색은 MCP Repository를 경유하며, 일반 서비스 데이터는 Backend에서 직접 처리합니다. 일반 데이터의 실제 DB 저장 전환은 별도로 검증해야 합니다.

| 담당 | 주 작업 폴더 | 책임 |
|---|---|---|
| 상옥 | `frontend/` | 화면, 입력, Backend Client, 결과·추가 질문 표시 |
| 다혁 | `backend/` | API, Agent 판단·Tool 선택, 응답 집계, 일반 데이터 저장 |
| 병훈 | `legal_mcp/` | MCP Tool, 검색·결과 변환, Repository |
| 지혜 | `database/` | Schema, 원문 수집, 정규화·Chunk·Embedding, 데이터 검증 |

계약 변경은 제공·소비 파트가 함께 합의하고 `tests/contract/fixtures/`, Schema, 테스트, 명세서를 함께 갱신합니다.

## 주요 폴더

```text
frontend/               Streamlit 화면과 Backend Client
backend/app/agents/     공통 Runtime, 분야별 Profile, Tool 선택
backend/app/routers/    HTTP Endpoint
backend/app/schemas/    공개 요청·응답
backend/app/providers/  LLM Provider
legal_mcp/tools/        search_laws, search_consultations, search_cases 등
legal_mcp/services/     검색 규칙·결과 가공
legal_mcp/repositories/ SQL·pgvector 조회
database/migrations/   PostgreSQL Schema
database/ingestion/    수집·정규화·Chunk·Embedding
tests/contract/        계약 Fixture와 테스트
docs/                  계획·구조·명세·개발 가이드
scripts/               실행·테스트 명령
```

자세한 책임은 [디렉터리 구조](./docs/architecture/디렉터리%20구조.md)를 확인하세요.

## 개발 환경과 실행

개인 PC에서 Frontend·Backend·MCP·PostgreSQL·Redis를 함께 실행하려면 [개인 포트폴리오용 Docker 실행 안내](./docs/DOCKER_LOCAL_SETUP.md)를 먼저 확인하세요. Docker Hub 이미지로 실제 검색 데이터까지 같은 결과를 재현하는 방법은 [Docker Hub 릴리스 안내](./docs/DOCKER_RELEASE.md)를 참고하세요.

요구사항: Python `>=3.12,<3.13`, Docker Desktop 또는 PostgreSQL 16 + pgvector. 아래 예시는 PowerShell 기준입니다.

```powershell
git clone https://github.com/jasnok/aio-01-p2-team2.git
cd aio-01-p2-team2
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item frontend/.env.example frontend/.env
Copy-Item backend/.env.example backend/.env
Copy-Item legal_mcp/.env.example legal_mcp/.env
Copy-Item database/.env.example database/.env
```

서비스별 가상환경은 [서비스별 실행 가이드](./docs/개발환경%20구성.md)를 참고하세요. 기존 DB 볼륨은 [데이터베이스 명세서](./docs/architecture/데이터베이스%20명세서.md)를 확인하고, 초기화를 위해 임의 삭제하지 않습니다.

### 개인 Docker 실행 설정

개인 포트폴리오 환경에서는 팀 서버 IP를 사용하지 않습니다. `frontend`·`backend`·`legal_mcp`·`database`의 서비스별 `.env.example`을 각각 `.env`로 복사한 뒤, 개인 PostgreSQL·Redis 비밀번호와 OpenAI API Key를 입력하고 Docker Compose를 실행합니다.

```powershell
Copy-Item frontend/.env.example frontend/.env
Copy-Item backend/.env.example backend/.env
Copy-Item legal_mcp/.env.example legal_mcp/.env
Copy-Item database/.env.example database/.env
docker compose up --build -d
docker compose ps
```

컨테이너 내부 연결은 `frontend → backend → mcp-server → postgres` 및 `backend → redis`라는 Compose 서비스명으로 처리합니다. 사용자 브라우저에서는 본인 PC의 IP와 공개 포트로 접근합니다. 현재 PC의 IP가 `192.100.200.232`이면 Frontend는 `http://192.100.200.232:8501`입니다.

PostgreSQL과 Redis 포트는 로컬 PC에만 열고, Frontend·Backend·MCP만 LAN에서 접근할 수 있게 구성했습니다. 법률 데이터 적재는 비용이 발생하는 별도 작업이며 회원·대화 이력은 개인 DB로 이전하지 않습니다. 전체 절차와 데이터 적재 명령은 [개인 포트폴리오용 Docker 실행 안내](./docs/DOCKER_LOCAL_SETUP.md)를 확인하세요.

## 화면 개편 — Sidebar 제거

Frontend는 Sidebar 없이 상단의 내 사례 분석 / FAQ / 질의 이력으로 이동합니다.
선택 분야는 상단에 유지하고 관리자 FAQ는 FAQ 화면 안에서 접근합니다.
법 검색·실제 사례 검색·판례 검색 메뉴와 QA 빠른 테스트는 제거했습니다.
Backend/MCP 검색 기능은 분석에서 재사용하므로 삭제하지 않았습니다.

법령·판례·상담사례는 제목 + 최대 150자 미리보기 + 상세보기로 통일했습니다.
사용자 화면과 다운로드에서 출처 버튼·별도 기관 출처·URL·출처 목록은 제거합니다.
원래 Evidence·source 데이터는 내부 검증용으로 유지하며 법령명·사건번호 등 내용 식별자는 표시합니다.

SSE는 내부 Tool 이름 대신 사용자 문구를 표시합니다. DB 대화 저장·Context 조회는 아직 미연결이며
후속 담당 요청은 [대화 저장 및 Context 연결](./docs/development/대화저장_후속담당_요청.md)에 정리했습니다.
이번 로컬 변경은 아직 원격 develop에 반영되지 않았습니다.

## API 계약

분석 요청:

```http
POST /api/legal/questions
```

```json
{
  "session_id": "web-uuid",
  "category": "consumer",
  "question": "신용카드 일시불 결제 후 할부로 전환했는데 물건이 배송되지 않았습니다. 카드사에 할부항변권을 행사할 수 있나요?"
}
```

주요 응답 필드:

| 필드 | 의미 |
|---|---|
| `related_laws` | 법령 Evidence 배열 |
| `consultations` | 상담사례 Evidence 배열 |
| `similar_cases` | 판례 Evidence 배열 |
| `sources` | 출처 목록. 본문 Evidence 배열을 대신하지 않음 |
| `status`, `termination_reason` | 완료·실패·중단 및 상세 사유 |
| `follow_up_questions` | 추가 확인 질문 |
| `is_mock` | Mock 여부. 실연동은 false |

별도 검색은 기존 `GET /api/legal/laws`, `GET /api/legal/cases`를 실제 Agent 검색에 연결하고, `GET /api/legal/consultations`를 추가하는 계획입니다. 개별 검색 응답의 `items` 계약 및 유형별 상태 표현은 구현 전에 합의합니다.

자세한 응답 필드는 [API 명세서](./docs/architecture/API%20명세서.md), Tool 형식은 [MCP 도구 명세서](./docs/architecture/MCP%20도구%20명세서.md)를 참고하세요. 실행 서버 변경이 아직 문서·원격 코드에 반영되지 않았다면 먼저 동기화합니다.

## 다음 개발 순서

1. 실행 서버의 최신 Backend 코드를 push하고 원격 develop과 차이를 확인한다.
2. 임대차·근로 내 사례 분석의 추가정보 확인 정책과 분야별 검색 Tool 범위를 확정한다.
3. DB 분야·자료 유형별 건수와 임베딩, MCP 필터를 검증한다. 자료 없음과 미호출을 구별한다.
4. Frontend 추가 질문 표시 및 별도 검색 3종, 사이드바 6개를 구현한다.
5. 소비자 대표 질문의 9건 화면 표시와 임대차·근로 정보 보완 전후를 E2E 검증한다.
6. 실제 저장소로 대체된 운영 Mock만 제거한다. 회원·FAQ·알림·이력은 저장소 전환 후 정리한다.

자세한 협업 절차는 [통합 가이드](./docs/development/개발%20통합%20가이드.md)를 참고하세요. 해당 가이드의 초기 퇴직금 중심 목표와 Mock 설명은 이 문서의 현재 목표에 맞춰 후속 갱신해야 합니다.

## 테스트와 검증

```powershell
.\scripts\test_all.ps1
python -m pytest tests/contract
python -m pytest frontend/tests
```

기본 CI는 실제 외부 서비스 없이 Fixture와 테스트용 Mock으로 계약을 검증합니다. 테스트용 Mock은 운영 가짜 데이터와 구분해서 유지합니다.

실서버 E2E에서는 다음을 기록합니다.

- 배포 커밋, 질문·category, request_id
- 선택·실행한 Tool, 유형별 반환 건수·문서 ID
- Backend 응답 및 Frontend 카드의 일치 여부
- 추가 정보 필요 / 검색 결과 없음 / 검색 실패의 구분
- 처리 시간, 출처 URL, 문서 관련성 및 중복 여부

예전 UI 테스트 자료는 [Frontend Mock 테스트 체크리스트](./docs/프론트엔드%20Mock%20테스트%20체크리스트.md), [FAQ 공개·비밀글 댓글 테스트 체크리스트](./docs/FAQ%20공개·비밀글%20댓글%20테스트%20체크리스트.md)에 있습니다. 운영 통합 완료의 증거로 사용하지 않습니다.

## 개발 규칙

1. 자신의 담당 폴더를 중심으로 작업하고 공통 계약 변경을 먼저 공유합니다.
2. 실제 검색되지 않은 법령·조문·판례·사건번호·URL을 생성하지 않습니다.
3. 검색 점수를 승소 가능성으로 표현하지 않습니다.
4. 운영 Mock은 실제 구현으로 대체 후 제거하고, 테스트 Fixture는 분리 유지합니다. 남아 있는 Mock은 명확히 표시합니다.
5. `.env`, API Key, DB 비밀번호와 개인정보를 commit하지 않습니다.
6. PR 전에 관련 테스트를 실행하고, 서버 배포 버전과 Git 커밋을 공유합니다.
7. PR 제목은 한글로 작성합니다.

자세한 내용은 [팀 개발 규칙](./docs/팀%20개발%20규칙.md)을 확인하세요.

## 기준 문서

- [최종 개발 계획](./docs/최종%20plan.md)
- [AI Agent 명세서](./docs/AI%20agent%20명세서.md)
- [API 명세서](./docs/architecture/API%20명세서.md)
- [디렉터리 구조](./docs/architecture/디렉터리%20구조.md)
- [개발 통합 및 연결 확인](./docs/development/개발%20통합%20가이드.md)
- [팀 합의 요청사항](./docs/팀%20합의%20요청사항.md)

## 현재 한계

- 원격 코드와 실행 서버에 차이가 있어 최신 동작을 재현하려면 배포 코드를 동기화해야 합니다.
- 실제 pgvector Hybrid Search와 공통 Runtime은 구현되어 있으나 검색 범위·추가정보 판단·결과 품질은 보완 중입니다.
- 9건 반환은 검색 정확성이나 최신 법령 여부를 보장하지 않습니다.
- 일반 서비스 데이터의 영속 저장과 운영 Mock 제거는 별도 작업입니다.
- `mcp_server/FOOD.py`는 초기 네트워크 연결 확인용 레거시입니다.
- 이 서비스는 법률 자문, 범죄 성립 판단 또는 승패 예측을 제공하지 않습니다.
