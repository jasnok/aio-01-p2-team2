import uuid
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.core.config import get_settings
from backend.app.routers.health import router as health_router
from backend.app.routers.integration_router import router as integration_router
from backend.app.routers.legal import router as legal_router
from backend.app.routers.legal_terms import router as legal_terms_router, term_run_router
from backend.app.routers.mock_api import router as mock_api_router
from backend.app.services.session_service import SessionStoreUnavailableError, sessions
from backend.app.providers.openai import close_async_clients
from backend.app.services.agent_run_service import close_active_runs


@asynccontextmanager
async def lifespan(app):
    async with AsyncExitStack() as cleanup:
        cleanup.push_async_callback(sessions.close)
        cleanup.push_async_callback(close_async_clients)
        cleanup.push_async_callback(close_active_runs)
        yield


app = FastAPI(
    lifespan=lifespan,
    title="LawPath Backend API",
    version="0.1.0",
    description="""
## LawPath 생활 법률 안내 Backend

Frontend는 이 API만 호출합니다. Mock 모드는 외부 연결 없이 계약을 확인하며,
실제 모드는 MCP 검색, PostgreSQL, Redis와 연결합니다. 실제 실행 상태와 SSE 이벤트는
Redis에 TTL 동안 보관하며, 중단된 작업 자체를 자동 재개하는 작업 큐는 포함하지 않습니다.

### 처음 시험하는 순서

1. `GET /health`로 서버 상태를 확인합니다.
2. 실제 모드는 회원가입 후 로그인하며, Demo 계정은 Mock 모드에서만 사용합니다.
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
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=list({"http://localhost:8501", "http://127.0.0.1:8501", settings.frontend_origin.rstrip("/")}),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "Last-Event-ID", "X-Guest-Id", "X-Mock-Scenario"],
)
app.include_router(health_router)
app.include_router(legal_router)
app.include_router(legal_terms_router)
app.include_router(term_run_router)
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


@app.exception_handler(SessionStoreUnavailableError)
async def run_store_error(request: Request, exc: SessionStoreUnavailableError):
    return error_response(503, "RUN_STORE_UNAVAILABLE", "실행 상태 저장소에 연결할 수 없습니다.", request)


@app.exception_handler(__import__('fastapi').HTTPException)
async def http_error(request: Request, exc):
    detail = exc.detail if isinstance(exc.detail, dict) else {}
    return error_response(exc.status_code, detail.get("code", "INVALID_REQUEST"), detail.get("message", "요청을 처리할 수 없습니다."), request, detail.get("field_errors"))
