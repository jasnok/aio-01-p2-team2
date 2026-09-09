import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routers.health import router as health_router
from app.routers.integration_router import router as integration_router
from app.routers.legal import router as legal_router
from app.routers.mock_api import router as mock_api_router


app = FastAPI(
    title="LawPath Backend API",
    version="0.1.0",
    description="""
## LawPath 생활 법률 안내 Backend

Frontend는 이 API만 호출합니다. 현재는 **Mock 모드**이므로 외부 MCP, PostgreSQL, Redis 없이
메모리 데이터로 동작하며, 서버를 다시 시작하면 생성한 데이터가 사라집니다.

### 처음 시험하는 순서

1. `GET /health`로 서버 상태를 확인합니다.
2. `POST /api/auth/login`으로 Demo 계정에 로그인합니다.
3. 응답의 `session_token`을 이후 요청 Header의 `Authorization: Bearer 토큰`에 넣습니다.
4. 비회원 요청에는 `X-Guest-Id`를 넣습니다.

비밀번호와 Session Token은 화면 캡처·로그·문서에 남기지 마세요.
""",
    openapi_tags=[
        {"name": "health", "description": "서버가 실행 중인지와 현재 Mock/실연동 상태를 확인합니다."},
        {"name": "legal", "description": "생활 법률 사례 분석과 법령·판례·용어 검색입니다."},
        {"name": "mock-api", "description": "Mock 모드의 인증, FAQ, 질문, 댓글, 이력, 알림 API입니다."},
        {"name": "integration-smoke-test", "description": "개발용 MCP 연결 확인 기능입니다. 기본적으로 비활성화됩니다."},
    ],
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501", "http://192.100.200.232:8501"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "Last-Event-ID", "X-Guest-Id", "X-Mock-Scenario"],
)
app.include_router(health_router)
app.include_router(legal_router)
app.include_router(integration_router)
app.include_router(mock_api_router)


def error_response(status_code: int, code: str, message: str, request: Request, field_errors: list[dict] | None = None) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": {"code": code, "message": message, "request_id": getattr(request.state, "request_id", str(uuid.uuid4())), "field_errors": field_errors or []}})


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request.state.request_id = f"req-{uuid.uuid4()}"
    response = await call_next(request)
    response.headers["X-Request-Id"] = request.state.request_id
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    fields = [{"field": ".".join(str(part) for part in item["loc"] if part != "body"), "reason": item["msg"]} for item in exc.errors()]
    return error_response(422, "VALIDATION_ERROR", "입력 내용을 확인해 주세요.", request, fields)


@app.exception_handler(__import__('fastapi').HTTPException)
async def http_error(request: Request, exc):
    detail = exc.detail if isinstance(exc.detail, dict) else {}
    return error_response(exc.status_code, detail.get("code", "INVALID_REQUEST"), detail.get("message", "요청을 처리할 수 없습니다."), request, detail.get("field_errors"))
