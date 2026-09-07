# 개발 통합 및 연결 확인 가이드

## 1. 첫 통합 목표

첫 목표는 퇴직금 질문 한 건을 네 팀원 PC에서 끝까지 연결하는 것이다.

```text
Frontend 질문
→ POST /api/legal/questions
→ LaborAgent
→ search_cases
→ Legal MCP
→ PostgreSQL + pgvector
→ 공식 판례 Top 3
→ Frontend 카드
```

## 2. 팀 서버 주소

| 서비스 | 담당 | 주소 |
|---|---|---|
| Frontend | 상옥 | `http://192.100.200.232:8501` |
| Backend | 다혁 | `http://192.100.200.195:8000` |
| Legal MCP | 병훈 | `http://192.100.200.72:8011` |
| PostgreSQL | 지혜 | `192.100.200.99:5434/legal_ai` |

실제 DB 비밀번호는 문서나 Git에 기록하지 않고 담당 서버의 `.env`에서만 관리한다.

## 3. 통합 전 준비

- 네 컴퓨터가 같은 네트워크에 연결되어 있는지 확인한다.
- 각 서버를 `127.0.0.1`이 아닌 `0.0.0.0`에 바인딩한다.
- Windows 방화벽에서 `8501`, `8000`, `8011`, `5434`의 사설 네트워크 접근을 허용한다.
- 환경변수의 IP와 포트가 이 문서와 일치하는지 확인한다.
- 각 파트의 단위 테스트를 먼저 통과시킨다.

## 4. QA 화면에서 한 번에 확인

Frontend `.env`에 다음을 설정하고 Streamlit을 재시작한다.

```env
FRONTEND_DATA_MODE=mock
FRONTEND_QA_MODE=true
TEAM_FRONTEND_URL=http://192.100.200.232:8501
TEAM_BACKEND_URL=http://192.100.200.195:8000
TEAM_MCP_URL=http://192.100.200.72:8011
TEAM_DATABASE_HOST=192.100.200.99
TEAM_DATABASE_PORT=5434
TEAM_DATABASE_USER=legal_user
TEAM_DATABASE_NAME=legal_ai
```

1. Frontend에 접속한다.
2. 법률 카테고리 하나를 선택한다.
3. 사이드바의 `QA 빠른 테스트` 아래에서 `팀 서버 연결 테스트`를 연다.
4. `전체 연결 테스트 실행`을 누른다.
5. 각 서비스의 성공 여부, 응답시간과 health 응답을 확인한다.

검사 경로:

```text
Frontend  GET /_stcore/health
Backend   GET /health
MCP       GET /health
DB        TCP :5434
```

DB 검사는 Frontend에서 SQL을 직접 실행하지 않고 포트 접근까지만 확인한다. DB 로그인, `SELECT 1`과 실제 검색 가능 여부는 Backend 또는 MCP health에서 확인한다.

## 5. PowerShell 직접 확인

```powershell
Invoke-RestMethod http://192.100.200.232:8501/_stcore/health
Invoke-RestMethod http://192.100.200.195:8000/health
Invoke-RestMethod http://192.100.200.72:8011/health
Test-NetConnection 192.100.200.99 -Port 5434
```

Backend health의 `dependencies.mcp`와 `dependencies.database`가 실제 상태를 반환해야 연쇄 연결이 완료된 것이다. 단순히 HTTP 200만 반환하면서 `mock`, `disabled` 또는 `not_connected`라면 해당 의존성은 아직 미연동 상태다.

## 6. API·Tool 직접 확인

Backend 질문 계약은 `POST /api/legal/questions`이다. 요청·응답 예시는 `tests/contract/fixtures`를 기준으로 한다.

MCP 연결 확인은 정식 법률 Tool인 `search_cases`, `search_laws`, `get_law_article`을 사용한다. 과거 Food MCP 연결 코드는 네트워크 학습용 레거시이며 정식 완료 기준에 포함하지 않는다.

## 7. 권장 병렬 브랜치

- `feature/frontend-local-mvp`
- `feature/backend-agent-runtime`
- `feature/mcp-legal-search-tools`
- `feature/db-legal-ingestion`

각 파트는 `tests/contract/fixtures`를 기준으로 독립 구현하고, 계약 변경이 필요하면 관련 담당자에게 먼저 공유한다.

## 8. 장애 확인 순서

1. 담당 서버 프로세스가 실행 중인지 확인한다.
2. 서버가 `0.0.0.0`에 바인딩됐는지 확인한다.
3. 현재 IP가 문서의 IP와 같은지 `ipconfig`로 확인한다.
4. Windows 방화벽 인바운드 규칙을 확인한다.
5. 다른 PC에서 포트 연결을 확인한다.
6. health 응답의 의존성 상태를 확인한다.
7. 계약 Fixture로 실제 질문 한 건을 호출한다.

Timeout은 연결 실패이며 Mock 성공으로 대체하지 않는다. 실패 화면에는 어느 구간에서 중단됐는지 표시한다.
