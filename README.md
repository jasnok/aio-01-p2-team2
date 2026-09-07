# LawPath 생활 법률 검색 AI Agent

사용자가 생활 법률 상황을 입력하면 분야별 Agent가 공식 법령과 유사 판례를 검색하고, 출처와 함께 이해하기 쉽게 정리하는 팀 프로젝트입니다.

이 저장소는 네 파트가 동시에 개발할 수 있는 실행 가능한 골조입니다. 현재 Mock 결과는 연결과 데이터 계약 확인용이며 실제 법률정보가 아닙니다.

## 1분 만에 구조 이해하기

```text
사용자
  ↓
frontend/   Streamlit 화면
  ↓ HTTP
backend/    FastAPI + 분야별 Agent + 실행 정책
  ↓ MCP
legal_mcp/  법령·판례 검색 Tool
  ↓
PostgreSQL + pgvector

database/   Open API 수집·정규화·Chunk·Embedding
```

Frontend와 Backend는 DB를 직접 조회하지 않습니다. 법률 검색 DB 조회는 Legal MCP의 Repository를 통해서만 수행합니다.

## 팀원별로 어디를 수정하나요?

| 담당 | 주 작업 폴더 | 하는 일 |
|---|---|---|
| 상옥 | `frontend/` | Streamlit 화면, 사용자 입력, 결과 카드 |
| 다혁 | `backend/` | FastAPI, AgentRuntime, LLM Provider, 정책 |
| 병훈 | `legal_mcp/` | MCP Tool, 검색 Service, Repository |
| 지혜 | `database/` | Schema, 수집, 정규화, Chunk, Embedding |

파트 사이 데이터 형식은 `tests/contract/fixtures/`에 있습니다. 이 파일을 변경할 때는 사용하는 파트와 제공하는 파트의 테스트를 함께 수정합니다.

## 주요 폴더

```text
frontend/              화면과 Backend Client
backend/app/agents/    분야별 Agent 설정과 공통 Runtime
backend/app/routers/   HTTP Endpoint
backend/app/schemas/   Frontend에 공개하는 요청·응답
backend/app/providers/ LLM Provider
legal_mcp/tools/       search_laws, search_cases, get_law_article
legal_mcp/services/    검색 규칙과 결과 가공
legal_mcp/repositories/SQL·pgvector 조회 경계
database/migrations/   PostgreSQL Schema
database/ingestion/    수집·정규화·Chunk·Embedding
tests/contract/        파트 사이 계약 테스트
docs/architecture/     구조와 계약 설명
scripts/               실행과 전체 테스트 명령
```

더 자세한 책임은 [디렉터리 구조](./docs/architecture/디렉터리%20구조.md)를 확인하세요.

## 개발 환경 준비

요구사항:

- Python `>=3.12,<3.13`
- Docker Desktop 또는 PostgreSQL 16 + pgvector
- PowerShell 기준

처음 한 번만 실행합니다.

```powershell
git clone https://github.com/jasnok/aio-01-p2-team2.git
cd aio-01-p2-team2
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

`.env`의 기본값은 한 컴퓨터에서 실행하는 기준입니다. 서비스를 다른 팀원 PC에서 실행한다면 `127.0.0.1`을 해당 PC의 내부 IPv4로 변경합니다. `.env`와 API Key는 절대 commit하지 않습니다.

서비스별 가상환경을 쓰려면 [서비스별 실행 가이드](./docs/개발환경%20구성.md)를 확인하세요.

## 실행 순서

### 1. PostgreSQL 실행

```powershell
docker compose up -d postgres
docker compose ps
```

기존 개발 볼륨이 예전 Schema로 생성됐다면 [데이터베이스 명세서](./docs/architecture/데이터베이스%20명세서.md)의 주의사항을 먼저 확인하세요.

### 2. Legal MCP 실행

```powershell
.\scripts\run_mcp.ps1
```

확인:

```powershell
Invoke-RestMethod http://127.0.0.1:8011/health
```

### 3. Backend 실행

새 PowerShell에서 가상환경을 활성화한 뒤 실행합니다.

```powershell
.\scripts\run_backend.ps1
```

확인:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

### 4. Frontend 실행

다른 PowerShell에서 실행합니다.

```powershell
.\scripts\run_frontend.ps1
```

브라우저에서 `http://127.0.0.1:8501`을 엽니다.

### Frontend만 단독으로 확인하기

현재 Frontend MVP는 기본값이 `FRONTEND_DATA_MODE=mock`이므로 Backend, MCP와 DB를 실행하지 않아도 됩니다.

```powershell
cd C:\dev\aio-01-p2-team2
.\.venv\Scripts\Activate.ps1
python -m streamlit run frontend\app.py
```

### Frontend에서 Backend API 사용하기

`frontend/.env`를 다음처럼 설정하고 Frontend를 재시작합니다.

```env
FRONTEND_DATA_MODE=api
BACKEND_API_URL=http://192.100.200.195:8000
```

`api` 모드에서는 사례 분석, 법령·판례·용어 검색, 인증, 공지 FAQ, 사용자 질문·댓글, 질의 이력과 알림이 Backend API를 사용합니다. `mock` 모드에서는 Backend 없이 기존 Frontend Session 기능을 그대로 확인할 수 있습니다.

홈에서 `임대차·주거`, `근로·임금`, `소비자·중고거래` 중 하나를 선택한 뒤 다음 기능을 확인합니다.

1. `내 사례 분석`에서 대표 질문을 불러오거나 5자 이상 입력합니다.
2. `법 검색`에서 현재 분야의 키워드를 검색합니다.
3. `실제 사례`에서 현재 분야의 키워드를 검색합니다.
4. `쉬운 법률 용어`에서 용어를 검색합니다.
5. `필요 서류`와 `다음 행동`을 체크하고 진행률·초기화를 확인합니다.
6. `FAQ`를 검색하고 답변을 펼칩니다.
7. `질의 이력`에서 결과를 다시 보거나 삭제합니다.
8. `FAQ`에서 공지형 FAQ와 최신 사용자 질문을 확인하고 Mock 질문을 작성합니다.
9. QA 모드에서 비회원·회원·관리자 역할을 바꿔 역할별 화면을 확인합니다.

모든 결과는 `DEMO MODE`로 표시되는 UI 확인용 예시입니다.

모든 Frontend 기능을 자동으로 한 번에 확인하려면 다음 명령을 실행합니다.

```powershell
python -m pytest frontend\tests
```

QA 버튼으로 여러 화면 상태를 빠르게 확인하려면 `.env`에서 다음 값을 사용합니다.

```text
FRONTEND_QA_MODE=true
```

Streamlit을 다시 실행하면 사이드바에 `QA 빠른 테스트`가 나타납니다. 임대차·근로·소비자 결과, 결과 없음, 긴 입력과 세션 초기화 상태를 버튼으로 불러올 수 있습니다. 일반 시연에서는 `false`로 둡니다.

### 발표용 데모와 추가 화면 기능

`.env`에서 아래 값을 켜고 Streamlit을 다시 실행하면 사이드바에서 대표 임대차 시나리오를 즉시 준비할 수 있습니다.

```text
FRONTEND_PRESENTATION_MODE=true
```

발표 순서는 `분야 선택 → 사례 분석 → 법령·판례 상세 확인 → Markdown 결과 저장`입니다. 일반 사용 때는 `false`로 둡니다.

현재 Frontend는 입력 품질 안내, 법령·판례 상세 펼쳐 보기, 분석 결과 Markdown 저장과 작은 화면용 레이아웃 보정을 지원합니다.

FAQ 하단에는 사용자 질문 제목이 답변 대기 우선·상태별 최신순으로 10건씩 표시됩니다. 공개글은 누구나 본문과 댓글을 확인·작성할 수 있고, 비밀글은 제목만 공개되며 작성자와 관리자만 본문과 댓글에 접근할 수 있습니다. 질문 작성 시 비밀글이 기본 선택됩니다. 비회원 질문·댓글은 비밀번호로 수정·삭제 권한을 확인하며 Mock 비회원 데이터는 7일, Mock 회원 데이터는 영구보관 예정으로 표시됩니다. 관리자 Mock 역할에는 공지 FAQ 관리와 비밀글 운영 화면이 나타납니다.

상단의 **로그인** 메뉴에서 실제 Backend 없이 회원가입·로그인·로그아웃과 회원·관리자 화면을 확인할 수 있습니다.

```text
회원: user@lawpath.demo / Demo1234!
관리자: admin@lawpath.demo / Admin1234!
```

실제 개인정보나 사용 중인 비밀번호를 입력하면 안 됩니다. 입력한 비밀번호 원문은 로그인·가입 성공 후 Session에서 제거하며, 실제 인증·Cookie·DB 저장 기능은 포함하지 않습니다.

상단 **알림** 메뉴는 현재 브라우저 Session의 Mock 데이터로 동작합니다. 사례 분석 완료·실패, 근거 부족, 질문 등록, 로그인·로그아웃 알림을 자동으로 만들며 개별 읽음·모두 읽음·삭제·관련 화면 이동을 확인할 수 있습니다. QA 모드에서는 답변 완료·이력 만료 예정·서버 연결 오류 알림도 즉시 생성할 수 있습니다.

상세 수동 점검 순서는 [Frontend Mock 테스트 체크리스트](./docs/프론트엔드%20Mock%20테스트%20체크리스트.md)와 [FAQ 공개·비밀글 댓글 테스트 체크리스트](./docs/FAQ%20공개·비밀글%20댓글%20테스트%20체크리스트.md)를 확인하세요.

## 현재 API 계약

질문 Endpoint:

```http
POST /api/legal/questions
```

```json
{
  "session_id": "web-uuid",
  "category": "labor",
  "question": "퇴직했는데 퇴직금을 받지 못했습니다."
}
```

지원 category:

- `housing`: 임대차·주거
- `labor`: 근로·임금
- `consumer`: 소비자·중고거래

자세한 응답 필드는 [API 명세서](./docs/architecture/API%20명세서.md), Tool 형식은 [MCP 도구 명세서](./docs/architecture/MCP%20도구%20명세서.md)를 확인하세요.

## 테스트

모든 테스트:

```powershell
.\scripts\test_all.ps1
```

계약 테스트만 실행:

```powershell
python -m pytest tests/contract
```

기본 CI에서는 OpenAI와 국가법령정보 Open API를 실제 호출하지 않습니다. 외부 서비스가 없어도 Fixture와 Mock Repository로 계약을 확인할 수 있어야 합니다.

## 개발 순서

첫 통합 목표는 다음 한 경로입니다.

```text
퇴직금 질문
→ LaborAgent
→ search_cases
→ Legal MCP
→ pgvector
→ 공식 판례 Top 3
→ Backend 응답
→ Frontend 표시
```

이 경로가 성공한 다음 HousingAgent, ConsumerAgent와 보조 화면을 확장합니다. 자세한 순서는 [통합 가이드](./docs/development/개발%20통합%20가이드.md)를 확인하세요.

## 개발 규칙

1. 자신의 담당 폴더를 중심으로 작업합니다.
2. 공통 계약을 바꾸기 전에 관련 담당자에게 공유합니다.
3. Mock은 응답과 화면에 `is_mock=true`를 표시합니다.
4. 검색되지 않은 법령, 조문, 판례, 사건번호, URL을 생성하지 않습니다.
5. 검색 점수를 승소 가능성으로 표현하지 않습니다.
6. `.env`, API Key, DB 비밀번호와 개인정보를 commit하지 않습니다.
7. PR 전에 `python -m pytest`를 실행합니다.
8. PR 제목은 한글로 작성합니다.

자세한 팀 규칙은 [팀 개발 규칙](./docs/팀%20개발%20규칙.md)을 확인하세요.

## 기준 문서

- [최종 개발 계획](./docs/최종%20plan.md)
- [AI Agent 명세서](./docs/AI%20agent%20명세서.md)
- [API 명세서](./docs/architecture/API%20명세서.md)
- [디렉터리 구조](./docs/architecture/디렉터리%20구조.md)
- [개발 통합 및 연결 확인](./docs/development/개발%20통합%20가이드.md)
- [팀 합의 요청사항](./docs/팀%20합의%20요청사항.md)

## 현재 한계

- Legal MCP의 법률 검색은 아직 Mock 호환 경로를 포함합니다.
- AgentRuntime과 실제 pgvector Hybrid Search는 후속 기능 PR에서 구현합니다.
- `mcp_server/FOOD.py`는 초기 네트워크 연결 확인용 레거시입니다.
- 이 서비스는 법률 자문, 범죄 성립 판단 또는 승패 예측을 제공하지 않습니다.
