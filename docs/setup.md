# 서비스별 개발환경 구성

## 공통 기준

- Python `>=3.12,<3.13`
- 모든 명령은 프로젝트 루트에서 실행한다.
- `.venv`와 `.env`는 Git에 올리지 않는다.
- 각 서버 담당자는 자기 서비스의 가상환경과 의존성만 설치한다.

## Frontend — 상옥 PC

```powershell
python -m venv frontend\.venv
frontend\.venv\Scripts\python -m pip install --upgrade pip
frontend\.venv\Scripts\python -m pip install -r frontend\requirements.txt
Copy-Item frontend\.env.example frontend\.env
```

`frontend/.env`에서 다혁 PC의 실제 주소를 설정한다.

```env
BACKEND_API_URL=http://192.100.200.195:8000
FRONTEND_REQUEST_TIMEOUT_SECONDS=30
```

실행:

```powershell
frontend\.venv\Scripts\python -m streamlit run frontend\app.py
```

팀원은 `http://상옥_PC_IP:8501`로 접속한다.

## Backend — 다혁 PC

```powershell
python -m venv backend\.venv
backend\.venv\Scripts\python -m pip install --upgrade pip
backend\.venv\Scripts\python -m pip install -r backend\requirements.txt
Copy-Item backend\.env.example backend\.env
```

`backend/.env`에서 병훈 PC의 MCP 주소와 LLM 설정을 입력한다.

```env
MCP_SERVER_URL=http://병훈_PC_IP:8001
```

실행:

```powershell
backend\.venv\Scripts\python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

## Legal MCP — 병훈 PC

```powershell
python -m venv legal_mcp\.venv
legal_mcp\.venv\Scripts\python -m pip install --upgrade pip
legal_mcp\.venv\Scripts\python -m pip install -r legal_mcp\requirements.txt
Copy-Item legal_mcp\.env.example legal_mcp\.env
```

`legal_mcp/.env`에서 지혜 PC의 DB 주소와 필요한 Provider Key를 설정한다.

```env
DATABASE_URL=postgresql://사용자:비밀번호@지혜_PC_IP:5434/legal_ai
```

현재 Mock HTTP 서버 실행:

```powershell
legal_mcp\.venv\Scripts\python -m uvicorn legal_mcp.server:app --host 0.0.0.0 --port 8001
```

실제 MCP transport가 구현되면 병훈 담당 실행 명령으로 교체한다.

## Database — 지혜 PC

PostgreSQL + pgvector 서버는 Docker로 실행하므로 Python 가상환경이 필수는 아니다.

```powershell
Copy-Item database\.env.example database\.env
docker compose --env-file database\.env up -d postgres
docker compose --env-file database\.env ps
```

Seed, Chunking, Embedding 또는 평가 스크립트를 실행할 때만 DB 작업용 가상환경을 생성한다.

```powershell
python -m venv database\.venv
database\.venv\Scripts\python -m pip install --upgrade pip
database\.venv\Scripts\python -m pip install -r database\requirements.txt
```

## 전체 테스트 환경 — 선택 사항

한 PC에서 저장소 전체 테스트를 수행할 때만 루트 개발 가상환경을 사용한다.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python -m pytest -q
```

## LAN 연결 확인

```text
팀원 브라우저
→ 상옥 Frontend :8501
→ 다혁 Backend :8000
→ 병훈 MCP :8001
→ 지혜 PostgreSQL :5432
```

각 서버는 다른 PC에서 접근할 수 있도록 `0.0.0.0`에 bind하고 Windows 방화벽에서 담당 포트의 사설 네트워크 접근을 허용한다.

