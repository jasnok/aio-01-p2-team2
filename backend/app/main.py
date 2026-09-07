import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.routers.health import router as health_router
from backend.app.routers.integration_router import router as integration_router
from backend.app.routers.legal import router as legal_router
from backend.app.routers.mock_api import router as mock_api_router


app = FastAPI(title="Legal AI Agent Backend", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501", "http://192.100.200.232:8501"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Guest-Id", "X-Mock-Scenario"],
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
