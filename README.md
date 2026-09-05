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

더 자세한 책임은 [디렉터리 구조](./docs/architecture/directory-structure.md)를 확인하세요.

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

서비스별 가상환경을 쓰려면 [서비스별 실행 가이드](./docs/setup.md)를 확인하세요.

## 실행 순서

### 1. PostgreSQL 실행

```powershell
docker compose up -d postgres
docker compose ps
```

기존 개발 볼륨이 예전 Schema로 생성됐다면 [Database 계약](./docs/architecture/database-schema.md)의 주의사항을 먼저 확인하세요.

### 2. Legal MCP 실행

```powershell
.\scripts\run_mcp.ps1
```

확인:

```powershell
Invoke-RestMethod http://127.0.0.1:8001/health
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

FAQ 하단에는 공개 사용자 질문이 최신순으로 10건씩 표시됩니다. Mock 비회원은 작성 후 7일, Mock 회원은 영구보관 예정 안내가 표시되며, 작성자는 답변 전 수정·삭제 또는 답변 후 `수정해서 다시 질문`을 사용할 수 있습니다. 관리자 Mock 역할에는 공지 FAQ 관리 메뉴가 나타납니다.

상세 수동 점검 순서는 [프론트엔드 테스트 체크리스트](./docs/프론트엔드%20테스트%20체크리스트.md)를 확인하세요.

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

자세한 응답 필드는 [Frontend–Backend API 계약](./docs/architecture/api-contract.md), Tool 형식은 [MCP Tool 계약](./docs/architecture/mcp-tool-contract.md)을 확인하세요.

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

이 경로가 성공한 다음 HousingAgent, ConsumerAgent와 보조 화면을 확장합니다. 자세한 순서는 [통합 가이드](./docs/development/integration-guide.md)를 확인하세요.

## 개발 규칙

1. 자신의 담당 폴더를 중심으로 작업합니다.
2. 공통 계약을 바꾸기 전에 관련 담당자에게 공유합니다.
3. Mock은 응답과 화면에 `is_mock=true`를 표시합니다.
4. 검색되지 않은 법령, 조문, 판례, 사건번호, URL을 생성하지 않습니다.
5. 검색 점수를 승소 가능성으로 표현하지 않습니다.
6. `.env`, API Key, DB 비밀번호와 개인정보를 commit하지 않습니다.
7. PR 전에 `python -m pytest`를 실행합니다.
8. PR 제목은 한글로 작성합니다.

자세한 팀 규칙은 [팀 개발 규칙](./docs/team-rules.md)을 확인하세요.

## 기준 문서

- [최종 개발 계획](./docs/최종%20plan.md)
- [AI Agent 명세서](./docs/AI%20agent%20명세서.md)
- [디렉터리 구조](./docs/architecture/directory-structure.md)
- [통합 Smoke Test](./docs/integration-smoke-test.md)

## 현재 한계

- Legal MCP의 법률 검색은 아직 Mock 호환 경로를 포함합니다.
- AgentRuntime과 실제 pgvector Hybrid Search는 후속 기능 PR에서 구현합니다.
- `mcp_server/FOOD.py`는 초기 네트워크 연결 확인용 레거시입니다.
- 이 서비스는 법률 자문, 범죄 성립 판단 또는 승패 예측을 제공하지 않습니다.
