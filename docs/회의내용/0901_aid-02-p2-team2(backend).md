# 법률 사례 검색 AI Agent — Backend 권장 폴더 구조

```text
backend/
├─ .env.example                     # 환경변수 이름과 안전한 기본값
├─ requirements.txt                 # Backend 전용 Python 패키지
├─ __init__.py                      # backend를 Python 패키지로 인식
│
├─ app/                             # Backend 애플리케이션 소스
│  ├─ __init__.py
│  ├─ main.py                       # FastAPI 생성 및 Router 등록
│  │
│  ├─ routers/                      # HTTP 요청 수신과 응답 반환
│  │  ├─ health.py                  # GET /health 및 의존 서비스 상태 확인
│  │  └─ legal.py                   # POST /api/legal/questions
│  │
│  ├─ schemas/                      # Pydantic 데이터 계약과 입력 검증
│  │  ├─ legal.py                   # 질문, 법률문서, 최종 응답 모델
│  │  └─ agent.py                   # Agent 입력, 결과, Trace 모델
│  │
│  ├─ services/                     # 질문 처리 전체 흐름과 공통 정책
│  │  └─ legal_question_service.py  # Agent 선택, 결과 검증, 응답 조립
│  │
│  ├─ agents/                       # 카테고리별 Tool 선택과 검색 판단
│  │  ├─ base.py                    # 세 Agent의 공통 규칙과 실행 제한
│  │  ├─ registry.py                # category에 맞는 Agent 선택
│  │  ├─ housing_agent.py           # 임대차·주거 전문 Agent
│  │  ├─ labor_agent.py             # 근로·임금 전문 Agent
│  │  └─ consumer_agent.py          # 중고거래·소비자 분쟁 전문 Agent
│  │
│  ├─ mcp_clients/                  # Backend와 MCP Server 통신
│  │  ├─ legal_mcp.py               # 초기 Mock REST 연결용 Client
│  │  └─ mcp_client.py              # 실제 MCP 프로토콜 연결용 Client
│  │
│  └─ core/                         # Backend 공통 기반 설정
│     ├─ config.py                  # .env 로딩 및 설정값 검증
│     └─ exceptions.py              # 공통 오류 정의(필요 시 추가)
│
└─ tests/                           # Backend 단위 테스트
   ├─ test_api.py                   # API 정상·오류 응답 테스트
   ├─ test_service.py               # Agent 선택과 응답 조립 테스트
   └─ test_agents.py                # Agent별 Tool 선택과 제한 테스트
```

## 요청 처리 흐름

```text
Frontend
  → Router                       HTTP 요청 수신
  → LegalQuestionService         공통 흐름 관리
  → Agent Registry               category로 Agent 선택
     ├─ housing  → HousingAgent
     ├─ labor    → LaborAgent
     └─ consumer → ConsumerAgent
  → MCP Client                   MCP Tool 호출
  → Legal MCP Server             법령·사례 검색
  → DB/RAG                       실제 근거 조회
  → Service                      출처 검증 및 공통 응답 조립
  → Frontend                     결과 반환
```

## 계층별 핵심 책임

| 계층 | 책임 |
|---|---|
| Router | HTTP 요청·응답과 상태 코드 |
| Service | 세 Agent의 공통 실행 흐름과 결과 통합 |
| Agent | 카테고리별 Tool 선택과 검색 전략 |
| MCP Client | MCP 서버 통신 |
| Schema | 요청·응답 데이터 검증 |
| Core | 환경설정과 공통 오류 |

## Service를 유지하는 이유

- 세 Agent의 공통 코드 중복 방지
- Router 비대화 방지
- 세 Agent의 결과를 동일한 API 응답으로 통일
- `request_id`, 출처, 오류, Trace를 한곳에서 관리
- Redis, SSE, 세션 기능의 중복 구현 방지

## Mock에서 실제 MCP로 전환

초기 테스트:

```text
legal_question_service.py → legal_mcp.py → FastAPI Mock MCP
```

최종 구조:

```text
legal_question_service.py → mcp_client.py → 실제 Legal MCP Server
```

실제 MCP 연결이 검증되면 `legal_mcp.py`는 테스트 전용으로 유지하거나 제거한다.

## 주의사항

- Backend와 Agent는 DB에 직접 접근하지 않는다.
- Agent는 Tool Result에 없는 법령·사건번호를 생성하지 않는다.
- 서버 주소와 API Key를 코드에 직접 작성하지 않는다.
- `schemas` 변경 전 Frontend·MCP 담당자와 공유한다.
- `__pycache__`는 자동 생성 폴더이므로 Git에 올리지 않는다.
