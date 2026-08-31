# Legal AI Agent

일상생활 법률 문제를 대상으로 법령과 유사 사례를 검색하고 출처와 함께 설명하는 팀 프로젝트입니다.

현재 단계는 네 대의 컴퓨터에서 `Frontend → Backend → Mock MCP` 연결을 검증하기 위한 실행 가능한 뼈대입니다. Mock 결과는 실제 법률 정보가 아닙니다.

## 기술 기준

- Python `>=3.12,<3.13`
- Frontend: Streamlit
- Backend: FastAPI
- MCP 개발 전 연결 계약: FastAPI 기반 Mock endpoint
- Database: PostgreSQL + pgvector

## 설치

```powershell
git clone https://github.com/jasnok/aio-01-p2-team2.git
cd aio-01-p2-team2
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

## 실행

### 1. MCP Mock Server

```powershell
uvicorn legal_mcp.server:app --host 0.0.0.0 --port 8001
```

### 2. Backend

다른 PC의 MCP에 연결한다면 `.env`의 `MCP_SERVER_URL`을 병훈 PC의 내부 IP로 변경합니다.

```powershell
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

### 3. Frontend

다른 PC의 Backend에 연결한다면 `.env`의 `BACKEND_API_URL`을 다혁 PC의 내부 IP로 변경합니다.

```powershell
streamlit run frontend/app.py --server.address 0.0.0.0 --server.port 8501
```

`.streamlit/config.toml`에 LAN 공개 설정이 포함되어 있으므로 다음 명령만 사용해도 됩니다.

```powershell
streamlit run frontend/app.py
```

상옥 PC의 IPv4가 `192.100.200.232`라면 같은 네트워크의 팀원은 `http://192.100.200.232:8501`로 접속합니다. IP는 네트워크 재접속 시 달라질 수 있으므로 실행 전에 `ipconfig`로 다시 확인합니다.

### 4. PostgreSQL + pgvector

```powershell
docker compose up -d postgres
docker compose ps
```

## 연결 확인

```powershell
Invoke-RestMethod http://127.0.0.1:8001/health
Invoke-RestMethod http://127.0.0.1:8000/health
```

Frontend에서 카테고리와 질문을 입력하면 Backend가 Mock MCP 결과를 받아 구조화된 답변을 반환합니다.

## 주의

- `.env`와 API Key를 commit하지 않습니다.
- Mock 결과에는 `is_mock=true`가 포함되며 실제 법률 정보로 사용하면 안 됩니다.
- 실제 MCP 프로토콜과 RAG 구현은 담당 feature 브랜치에서 Mock 계약을 대체합니다.

상세 설계와 역할은 [1차_plan.md](./1차_plan.md)를 참고합니다.
