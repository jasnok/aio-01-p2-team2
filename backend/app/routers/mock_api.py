from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from math import ceil
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Security
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, field_validator

from backend.app.services.mock_store import SessionExpiredError, hash_password, iso, now, store, verify_password
from backend.app.services.agent_run_service import create_run, public_run, start_run
from backend.app.core.config import get_settings
from backend.app.repositories.user_repository import DuplicateEmailError
from backend.app.services.auth_service import AuthService, InactiveUserError, InvalidCredentialsError
from backend.app.services.session_service import SessionStoreUnavailableError, sessions
from backend.app.repositories.saved_conversation_repository import SavedConversationNotFoundError
from backend.app.services.saved_conversation_service import SavedConversationService
from backend.app.services.guest_session_service import guest_sessions
from backend.app.mock_data.catalog import CATALOG

router = APIRouter(prefix="/api", tags=["mock-api"])
Category = Literal["housing", "labor", "consumer"]
auth_service = AuthService()
saved_conversation_service = SavedConversationService()
bearer_scheme = HTTPBearer(auto_error=False, description="로그인 응답의 session_token을 붙여 넣습니다. Swagger에는 토큰값만 입력하세요.")


def fail(status: int, code: str, message: str) -> None:
    raise HTTPException(status_code=status, detail={"code": code, "message": message})


def actor(credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme), x_guest_id: str | None = Header(default=None, description="비회원의 브라우저 세션을 구분하는 UUID입니다.")) -> dict:
    token = credentials.credentials if credentials else None
    try:
        return store.actor_for_token(token, x_guest_id)
    except SessionExpiredError:
        fail(401, "AUTH_SESSION_EXPIRED", "로그인 세션이 만료되었습니다. 다시 로그인해 주세요.")
    except PermissionError:
        fail(401, "AUTH_REQUIRED", "로그인이 필요하거나 세션이 만료되었습니다.")


async def database_or_mock_actor(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    x_guest_id: str | None = Header(default=None),
) -> dict:
    """Use DB-backed tokens in real mode without changing the Mock API contract."""
    if get_settings().backend_mock_mode:
        return legacy_actor(credentials, x_guest_id)

    token = credentials.credentials if credentials else None
    if not token:
        return {"id": x_guest_id or "guest-anonymous", "role": "GUEST", "display_name": "비회원"}
    try:
        session = await sessions.read(token)
        value = await auth_service.actor(session.user_id) if session else None
    except SessionStoreUnavailableError:
        fail(503, "SESSION_UNAVAILABLE", "로그인 세션을 확인할 수 없습니다.")
    if value is None:
        fail(401, "AUTH_REQUIRED", "로그인이 필요하거나 세션이 만료되었습니다.")
    return value


# Existing routes below resolve this name at declaration time.
legacy_actor = actor
actor = database_or_mock_actor


def require_user(value: dict = Depends(actor)) -> dict:
    if value["role"] == "GUEST":
        fail(401, "AUTH_REQUIRED", "로그인이 필요합니다.")
    return value


def require_admin(value: dict = Depends(actor)) -> dict:
    if value["role"] != "ADMIN":
        fail(403, "FORBIDDEN", "관리자 권한이 필요합니다.")
    return value


def page(items: list[dict], number: int, size: int) -> dict:
    total = len(items)
    pages = max(1, ceil(total / size))
    number = min(number, pages)
    return {"items": items[(number - 1) * size:number * size], "pagination": {"page": number, "page_size": size, "total_items": total, "total_pages": pages, "has_previous": number > 1, "has_next": number < pages}}


def question_view(question: dict, value: dict, detail: bool = False) -> dict:
    owner = question["owner_id"] == value["id"]
    allowed = question["visibility"] == "PUBLIC" or owner or value["role"] == "ADMIN"
    result = {key: question[key] for key in ("id", "category", "title", "status", "visibility", "display_name", "created_at", "updated_at", "expires_at")}
    result.update({"content_visibility": "PUBLIC" if question["visibility"] == "PUBLIC" else "OWNER_ONLY", "is_owner": owner})
    if detail:
        if not allowed:
            fail(403, "FORBIDDEN", "비밀글은 작성자 또는 관리자만 열람할 수 있습니다.")
        result.update({"content": question["content"], "answer": question.get("answer"), "parent_question_id": question.get("parent_question_id")})
        if value["role"] == "ADMIN" and question["visibility"] == "PRIVATE" and not owner:
            store.audit(value, "PRIVATE_QUESTION_VIEWED", question["id"])
    return result


def get_question(question_id: str) -> dict:
    item = store.questions.get(question_id)
    if not item:
        fail(404, "NOT_FOUND", "질문을 찾을 수 없습니다.")
    return item


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254, description="로그인할 이메일 주소입니다.", examples=["user@lawpath.demo"])
    password: str = Field(min_length=8, max_length=128, description="비밀번호입니다. 응답과 로그에는 저장·표시되지 않습니다.", examples=["Demo1234!"])

    @field_validator("email")
    @classmethod
    def email_valid(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value or value.startswith("@"):
            raise ValueError("이메일 형식을 확인해 주세요.")
        return value


class Register(Credentials):
    display_name: str = Field(min_length=2, max_length=30, description="화면에 표시할 이름입니다.", examples=["법률초보"])


class PasswordReset(BaseModel):
    email: str = Field(min_length=3, max_length=254, description="재설정 안내를 요청할 이메일입니다.")


@router.get("/catalog/categories")
def catalog_categories() -> dict:
    return {"items": [{"id": key, "name": value["name"], "representative_questions": value["representative_questions"]} for key, value in CATALOG.items()]}


@router.get("/catalog/{category}")
def catalog_detail(category: Category) -> dict:
    return {"category": category, **CATALOG[category]}


@router.post("/auth/register", status_code=201, summary="회원가입", description="새 회원을 만들고 바로 사용할 수 있는 Session Token을 발급합니다.")
async def register(body: Register) -> dict:
    if not get_settings().backend_mock_mode:
        try:
            user = await auth_service.register(body.email, body.password, body.display_name)
            token, expires_in = await sessions.issue(user.id)
        except DuplicateEmailError:
            fail(409, "CONFLICT", "이미 사용 중인 이메일입니다.")
        except SessionStoreUnavailableError:
            fail(503, "SESSION_UNAVAILABLE", "회원가입은 완료됐지만 로그인 세션을 만들 수 없습니다. 다시 로그인해 주세요.")
        return {"session_token": token, "expires_in": expires_in, "user": user.public()}
    if any(item["email"] == body.email for item in store.users.values()):
        fail(409, "CONFLICT", "이미 사용 중인 이메일입니다.")
    user_id = f"user-{uuid4()}"
    user = {"id": user_id, "email": body.email, "display_name": body.display_name.strip(), "role": "USER", "password_hash": hash_password(body.password)}
    store.users[user_id] = user
    token, public = store.issue_session(user)
    store.notify(user_id, "REGISTERED", "회원가입 완료", "회원가입이 완료되었습니다.", severity="success")
    return {"session_token": token, "expires_in": 28800, "user": public}


@router.post("/auth/login", summary="로그인", description="이메일과 비밀번호를 확인하고 8시간짜리 Opaque Session Token을 발급합니다.")
async def login(body: Credentials) -> dict:
    if not get_settings().backend_mock_mode:
        try:
            user = await auth_service.login(body.email, body.password)
            token, expires_in = await sessions.issue(user.id)
        except (InvalidCredentialsError, InactiveUserError):
            fail(401, "AUTH_REQUIRED", "이메일 또는 비밀번호가 올바르지 않습니다.")
        except SessionStoreUnavailableError:
            fail(503, "SESSION_UNAVAILABLE", "로그인 세션을 만들 수 없습니다. 잠시 후 다시 시도해 주세요.")
        return {"session_token": token, "expires_in": expires_in, "user": user.public()}
    user = next((item for item in store.users.values() if item["email"] == body.email), None)
    if not user or not verify_password(body.password, user["password_hash"]):
        fail(401, "AUTH_REQUIRED", "이메일 또는 비밀번호가 올바르지 않습니다.")
    token, public = store.issue_session(user)
    store.notify(user["id"], "LOGGED_IN", "로그인", "로그인되었습니다.", severity="success")
    return {"session_token": token, "expires_in": 28800, "user": public}


@router.post("/auth/logout", status_code=204, summary="로그아웃", description="현재 Bearer Session Token을 즉시 폐기합니다. Swagger 오른쪽 위 Authorize에서 로그인 토큰을 설정한 뒤 실행하세요.")
async def logout(credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme)) -> None:
    token = credentials.credentials if credentials else None
    if not get_settings().backend_mock_mode:
        try:
            revoked = await sessions.revoke(token)
        except SessionStoreUnavailableError:
            fail(503, "SESSION_UNAVAILABLE", "로그인 세션을 처리할 수 없습니다.")
        if not revoked:
            fail(401, "AUTH_REQUIRED", "로그인이 필요합니다.")
        return
    session = store.sessions.pop(token, None) if token else None
    if not session:
        fail(401, "AUTH_REQUIRED", "로그인이 필요합니다.")
    store.notify(session["user_id"], "LOGGED_OUT", "로그아웃", "로그아웃되었습니다.")


@router.get("/auth/me", summary="내 로그인 상태 확인", description="현재 Token 또는 Guest ID 기준의 역할과 이력 보관 정책을 보여줍니다.")
def me(value: dict = Depends(actor)) -> dict:
    return {"user": value, "authenticated": value["role"] != "GUEST", "history_policy": "영구 보관" if value["role"] != "GUEST" else "7일 보관"}


@router.post("/auth/password-reset", summary="비밀번호 재설정 요청", description="계정 존재 여부를 공개하지 않습니다. Mock 모드에서는 이메일을 보내지 않습니다.")
def password_reset(body: PasswordReset) -> dict:
    return {"message": "등록 여부와 관계없이 재설정 안내를 처리했습니다. Mock 모드에서는 이메일을 발송하지 않습니다."}


@router.get("/faqs", summary="공개 FAQ 조회", description="누구나 조회할 수 있습니다. 고정 FAQ가 먼저, 그 다음 표시 순서대로 반환됩니다.")
def faqs(category: Category | None = None) -> dict:
    items = [item.copy() for item in store.faqs.values() if item["is_active"] and (category is None or item["category"] == category)]
    items.sort(key=lambda item: datetime.fromisoformat(item["updated_at"]).timestamp(), reverse=True)
    items.sort(key=lambda item: item["display_order"])
    items.sort(key=lambda item: item["is_pinned"], reverse=True)
    return {"items": items}


class FaqBody(BaseModel):
    category: Category
    question: str = Field(min_length=2, max_length=500, description="FAQ의 질문 문장입니다.")
    answer: str = Field(min_length=2, max_length=5000, description="사용자에게 보여 줄 안내 답변입니다.")
    is_active: bool = True
    is_pinned: bool = False
    display_order: int = Field(default=999, ge=0)


@router.get("/admin/faqs", summary="관리자 FAQ 전체 조회", description="비활성 FAQ를 포함해 관리용 목록을 봅니다. ADMIN만 사용할 수 있습니다.")
def admin_faqs(_: dict = Depends(require_admin)) -> dict:
    return {"items": sorted(store.faqs.values(), key=lambda item: item["display_order"])}


@router.post("/admin/faqs", status_code=201, summary="관리자 FAQ 등록", description="새 FAQ를 등록합니다. ADMIN만 사용할 수 있습니다.")
def add_faq(body: FaqBody, _: dict = Depends(require_admin)) -> dict:
    faq = {"id": f"faq-{uuid4()}", **body.model_dump(), "updated_at": iso()}
    store.faqs[faq["id"]] = faq
    return faq


@router.patch("/admin/faqs/{faq_id}", summary="관리자 FAQ 수정", description="FAQ 내용·공개 여부·고정 여부·순서를 바꿉니다.")
def edit_faq(faq_id: str, body: FaqBody, _: dict = Depends(require_admin)) -> dict:
    if faq_id not in store.faqs:
        fail(404, "NOT_FOUND", "FAQ를 찾을 수 없습니다.")
    store.faqs[faq_id].update(body.model_dump() | {"updated_at": iso()})
    return store.faqs[faq_id]


@router.delete("/admin/faqs/{faq_id}", status_code=204, summary="관리자 FAQ 삭제", description="FAQ를 삭제합니다. Mock 데이터에서는 복구할 수 없습니다.")
def delete_faq(faq_id: str, _: dict = Depends(require_admin)) -> None:
    if not store.faqs.pop(faq_id, None):
        fail(404, "NOT_FOUND", "FAQ를 찾을 수 없습니다.")


class QuestionBody(BaseModel):
    category: Category
    title: str = Field(min_length=2, max_length=100, description="목록에 공개되는 질문 제목입니다.")
    content: str = Field(min_length=10, max_length=2000, description="질문의 자세한 내용입니다. 비밀글은 작성자·관리자만 볼 수 있습니다.")
    post_password: str = Field(min_length=4, max_length=20, description="질문 수정·삭제·잠금 해제에 쓰는 비밀번호입니다. Hash만 저장됩니다.")
    visibility: Literal["PUBLIC", "PRIVATE"] = Field(default="PRIVATE", description="PUBLIC은 누구나 본문을 보고 댓글을 쓸 수 있고, PRIVATE는 작성자·관리자만 접근합니다.")
    privacy_confirmed: bool = Field(description="개인정보 처리 안내를 확인했다는 동의 값입니다. true여야 등록됩니다.")


class UnlockBody(BaseModel): post_password: str = Field(min_length=4, max_length=20)
class QuestionDeleteBody(BaseModel):
    post_password: str | None = Field(default=None, min_length=4, max_length=20, description="작성자 삭제 시 필요한 게시글 비밀번호입니다.")
    reason: str | None = Field(default=None, min_length=2, max_length=500, description="관리자 삭제 시 필수인 운영·신고 처리 사유입니다.")
class EditQuestion(BaseModel):
    title: str = Field(min_length=2, max_length=100)
    content: str = Field(min_length=10, max_length=2000)
    post_password: str = Field(min_length=4, max_length=20)
    visibility: Literal["PUBLIC", "PRIVATE"] | None = None
class AnswerBody(BaseModel): answer: str = Field(min_length=2, max_length=5000)


@router.get("/questions", summary="질문 목록 조회", description="제목은 모든 사람에게 보입니다. 답변 대기(PENDING)가 먼저, 같은 상태에서는 최신 질문이 먼저 나옵니다.")
def list_questions(value: dict = Depends(actor), page_number: int = Query(1, alias="page", ge=1), page_size: int = Query(10, ge=1, le=50), category: Category | None = None, status: Literal["PENDING", "ANSWERED"] | None = None, query: str = Query("", max_length=200)) -> dict:
    query = query.strip().lower()
    items = []
    for item in store.questions.values():
        searchable = item["title"] + (" " + item["content"] if item["visibility"] == "PUBLIC" else "")
        if (category and item["category"] != category) or (status and item["status"] != status) or (query and query not in searchable.lower()):
            continue
        items.append(question_view(item, value))
    items.sort(key=lambda item: (0 if item["status"] == "PENDING" else 1, item["created_at"], item["id"]), reverse=False)
    # keep PENDING first, but newest first within each state
    items.sort(key=lambda item: (0 if item["status"] == "PENDING" else 1, -__import__('datetime').datetime.fromisoformat(item["created_at"]).timestamp(), item["id"]))
    return page(items, page_number, page_size)


@router.post("/questions", status_code=201, summary="질문 작성", description="회원과 비회원 모두 작성할 수 있습니다. 기본값은 비밀글(PRIVATE)입니다. 비회원은 X-Guest-Id Header가 필요합니다.")
def create_question(body: QuestionBody, value: dict = Depends(actor)) -> dict:
    if not body.privacy_confirmed:
        fail(422, "VALIDATION_ERROR", "개인정보 처리 안내에 동의해 주세요.")
    question_id = f"question-{uuid4()}"
    question = {"id": question_id, "owner_id": value["id"], "display_name": value["display_name"], "category": body.category, "title": body.title.strip(), "content": body.content.strip(), "password_hash": hash_password(body.post_password), "visibility": body.visibility, "status": "PENDING", "answer": None, "created_at": iso(), "updated_at": iso(), "expires_at": iso(now() + timedelta(days=7)) if value["role"] == "GUEST" else None}
    store.questions[question_id] = question
    store.history.setdefault(value["id"], []).append({"id": f"history-{uuid4()}", "type": "user_question", "target_id": question_id, "category": body.category, "title": question["title"], "created_at": question["created_at"]})
    store.notify(value["id"], "QUESTION_CREATED", "질문 등록", "질문이 등록되었습니다.", target_type="question", target_id=question_id, category=body.category, severity="success")
    return question_view(question, value, detail=True)


@router.get("/questions/{question_id}", summary="질문 상세 조회", description="공개글은 모두 볼 수 있습니다. 비밀글은 작성자와 관리자만 볼 수 있습니다.")
def question_detail(question_id: str, value: dict = Depends(actor)) -> dict:
    return question_view(get_question(question_id), value, detail=True)


@router.post("/questions/{question_id}/unlock", summary="비밀글 잠금 해제", description="작성자가 게시글 비밀번호를 확인하면 현재 세션에 10분짜리 열람 권한을 기록합니다.")
def unlock(question_id: str, body: UnlockBody, value: dict = Depends(actor)) -> dict:
    question = get_question(question_id)
    if question["owner_id"] != value["id"]:
        fail(403, "FORBIDDEN", "작성자만 잠금을 해제할 수 있습니다.")
    if not verify_password(body.post_password, question["password_hash"]):
        fail(403, "FORBIDDEN", "게시글 비밀번호가 올바르지 않습니다.")
    store.unlocks[(value["id"], question_id)] = now() + timedelta(minutes=10)
    return {"unlocked": True, "expires_at": iso(store.unlocks[(value["id"], question_id)])}


@router.patch("/questions/{question_id}", summary="질문 수정", description="작성자만 수정할 수 있으며 답변 대기(PENDING) 질문만 수정됩니다.")
def update_question(question_id: str, body: EditQuestion, value: dict = Depends(actor)) -> dict:
    question = get_question(question_id)
    if question["owner_id"] != value["id"] or not verify_password(body.post_password, question["password_hash"]):
        fail(403, "FORBIDDEN", "작성자와 게시글 비밀번호를 확인해 주세요.")
    if question["status"] != "PENDING":
        fail(409, "CONFLICT", "답변 완료 질문은 다시 질문 기능을 사용해 주세요.")
    question.update({"title": body.title.strip(), "content": body.content.strip(), "updated_at": iso()})
    if body.visibility: question["visibility"] = body.visibility
    return question_view(question, value, detail=True)


@router.delete("/questions/{question_id}", status_code=204, summary="질문 삭제", description="작성자는 비밀번호 확인 후 삭제합니다. 관리자는 모든 질문을 삭제할 수 있지만 reason을 반드시 입력하며 감사 로그가 남습니다.")
def remove_question(question_id: str, body: QuestionDeleteBody, value: dict = Depends(actor)) -> None:
    question = get_question(question_id)
    if value["role"] == "ADMIN":
        if not body.reason:
            fail(422, "VALIDATION_ERROR", "관리자 삭제 사유를 입력해 주세요.")
        store.audit(value, "QUESTION_DELETED_BY_ADMIN", question_id, body.reason.strip())
    elif question["owner_id"] != value["id"] or not verify_password(body.post_password or "", question["password_hash"]):
        fail(403, "FORBIDDEN", "작성자와 게시글 비밀번호를 확인해 주세요.")
    store.questions.pop(question_id)


@router.post("/questions/{question_id}/resubmit", status_code=201, summary="답변 완료 질문 다시 등록", description="기존 ANSWERED 질문을 바꾸지 않고, 연결된 새 PENDING 질문을 만듭니다.")
def resubmit(question_id: str, body: QuestionBody, value: dict = Depends(actor)) -> dict:
    original = get_question(question_id)
    if original["owner_id"] != value["id"]:
        fail(403, "FORBIDDEN", "작성자만 다시 질문할 수 있습니다.")
    result = create_question(body, value)
    store.questions[result["id"]]["parent_question_id"] = question_id
    return result


@router.patch("/admin/questions/{question_id}/answer", summary="관리자 답변 등록", description="ADMIN만 답변을 등록할 수 있고 질문 상태는 ANSWERED가 됩니다.")
def answer(question_id: str, body: AnswerBody, value: dict = Depends(require_admin)) -> dict:
    question = get_question(question_id)
    question.update({"answer": body.answer.strip(), "status": "ANSWERED", "updated_at": iso()})
    store.notify(question["owner_id"], "QUESTION_ANSWERED", "답변 등록", "등록한 질문에 답변이 작성되었습니다.", target_type="question", target_id=question_id, category=question["category"], severity="success")
    return question_view(question, value, detail=True)


class CommentBody(BaseModel):
    content: str = Field(min_length=2, max_length=1000, description="댓글 내용입니다.")
    comment_password: str | None = Field(default=None, min_length=4, max_length=20, description="비회원 댓글을 수정·삭제할 때 필요한 비밀번호입니다. 회원은 입력하지 않습니다.")


class CommentDeleteBody(BaseModel):
    comment_password: str | None = Field(default=None, min_length=4, max_length=20, description="비회원이 자신의 댓글을 삭제할 때 필요한 비밀번호입니다.")


def can_view_comments(question: dict, value: dict) -> bool:
    return question["visibility"] == "PUBLIC" or question["owner_id"] == value["id"] or value["role"] == "ADMIN"


@router.get("/questions/{question_id}/comments", summary="댓글 목록 조회", description="공개글은 모두 볼 수 있고, 비밀글은 작성자·관리자만 볼 수 있습니다.")
def list_comments(question_id: str, value: dict = Depends(actor), page_number: int = Query(1, alias="page", ge=1), page_size: int = Query(20, ge=1, le=50)) -> dict:
    question = get_question(question_id)
    if not can_view_comments(question, value): fail(403, "FORBIDDEN", "비밀글 댓글은 작성자 또는 관리자만 볼 수 있습니다.")
    if value["role"] == "ADMIN" and question["visibility"] == "PRIVATE" and question["owner_id"] != value["id"]: store.audit(value, "PRIVATE_COMMENTS_VIEWED", question_id)
    items = [item.copy() for item in store.comments.values() if item["question_id"] == question_id]
    items.sort(key=lambda item: (item["created_at"], item["id"]))
    for item in items: item.pop("password_hash", None); item["is_owner"] = item["owner_id"] == value["id"]
    return page(items, page_number, page_size)


@router.post("/questions/{question_id}/comments", status_code=201, summary="댓글 작성", description="공개글에는 누구나, 비밀글에는 질문 작성자와 관리자만 작성할 수 있습니다.")
def add_comment(question_id: str, body: CommentBody, value: dict = Depends(actor)) -> dict:
    question = get_question(question_id)
    if not can_view_comments(question, value): fail(403, "FORBIDDEN", "비밀글에는 작성자 또는 관리자만 댓글을 작성할 수 있습니다.")
    if value["role"] == "GUEST" and not body.comment_password: fail(422, "VALIDATION_ERROR", "비회원 댓글 비밀번호를 입력해 주세요.")
    comment_id = f"comment-{uuid4()}"
    comment = {"id": comment_id, "question_id": question_id, "owner_id": value["id"], "display_name": value["display_name"], "content": body.content.strip(), "password_hash": hash_password(body.comment_password) if body.comment_password else None, "created_at": iso(), "updated_at": iso(), "expires_at": question["expires_at"] if value["role"] == "GUEST" else None}
    store.comments[comment_id] = comment
    message = "새 댓글이 등록되었습니다." if question["visibility"] == "PUBLIC" else "비밀 질문에 새 댓글이 등록되었습니다."
    store.notify(question["owner_id"], "COMMENT_CREATED", "댓글 등록", message, target_type="question", target_id=question_id, category=question["category"])
    result = comment.copy(); result.pop("password_hash"); result["is_owner"] = True
    return result


@router.patch("/questions/{question_id}/comments/{comment_id}", summary="댓글 수정", description="댓글 작성자만 수정할 수 있습니다. 관리자는 다른 사람 댓글을 수정할 수 없습니다.")
def update_comment(question_id: str, comment_id: str, body: CommentBody, value: dict = Depends(actor)) -> dict:
    comment = store.comments.get(comment_id)
    if not comment or comment["question_id"] != question_id: fail(404, "NOT_FOUND", "댓글을 찾을 수 없습니다.")
    if comment["owner_id"] != value["id"] or (value["role"] == "GUEST" and not verify_password(body.comment_password or "", comment["password_hash"])): fail(403, "FORBIDDEN", "작성자만 댓글을 수정할 수 있습니다.")
    comment.update({"content": body.content.strip(), "updated_at": iso()})
    result = comment.copy(); result.pop("password_hash"); result["is_owner"] = True
    return result


@router.delete("/questions/{question_id}/comments/{comment_id}", status_code=204, summary="댓글 삭제", description="작성자는 자신의 댓글을 삭제할 수 있고, 관리자는 운영 목적으로 다른 사람 댓글을 삭제할 수 있습니다.")
def remove_comment(question_id: str, comment_id: str, body: CommentDeleteBody | None = None, value: dict = Depends(actor)) -> None:
    comment = store.comments.get(comment_id)
    if not comment or comment["question_id"] != question_id: fail(404, "NOT_FOUND", "댓글을 찾을 수 없습니다.")
    owner = comment["owner_id"] == value["id"] and (value["role"] != "GUEST" or verify_password((body.comment_password if body else "") or "", comment["password_hash"]))
    if not owner and value["role"] != "ADMIN": fail(403, "FORBIDDEN", "작성자만 댓글을 삭제할 수 있습니다.")
    if value["role"] == "ADMIN" and not owner: store.audit(value, "COMMENT_DELETED_BY_ADMIN", comment_id)
    store.comments.pop(comment_id)


class AgentRunCreate(BaseModel):
    category: Category
    question: str = Field(min_length=5, max_length=2000, description="분석할 생활 법률 질문입니다.")
    save_selected: bool = Field(default=False, description="사용자가 선택한 경우에만 대화와 근거를 저장합니다.")
    conversation_id: int | None = Field(default=None, gt=0, description="후속 질문에 사용할 본인 소유의 저장 대화 ID입니다.")

    @field_validator("question", mode="before")
    @classmethod
    def trim_question(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value


def get_run(run_id: str, value: dict) -> dict:
    run = store.agent_runs.get(run_id)
    if not run:
        fail(404, "NOT_FOUND", "Agent 실행 정보를 찾을 수 없습니다.")
    if run["owner_id"] != value["id"]:
        # 존재 여부도 노출하지 않아 ID 추측으로 다른 사용자의 분석을 볼 수 없다.
        fail(404, "NOT_FOUND", "Agent 실행 정보를 찾을 수 없습니다.")
    return run


def get_run_for_save(run_id: str, value: dict) -> dict:
    run = store.agent_runs.get(run_id)
    if not run:
        fail(404, "NOT_FOUND", "저장할 분석 결과를 찾을 수 없습니다.")
    if run["owner_id"] != value["id"]:
        fail(403, "FORBIDDEN", "다른 회원의 분석 결과는 저장할 수 없습니다.")
    return run


@router.post("/agent-runs", status_code=202, summary="비동기 Agent 분석 시작", description="즉시 run_id를 돌려주고 실제 분석은 백그라운드에서 진행합니다. 같은 소유자와 Idempotency-Key로 같은 본문을 다시 보내면 기존 작업을 반환합니다.")
async def create_agent_run(body: AgentRunCreate, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), value: dict = Depends(actor)) -> dict:
    if not idempotency_key or not idempotency_key.strip():
        fail(400, "INVALID_REQUEST", "Idempotency-Key Header가 필요합니다.")
    if body.save_selected and not get_settings().backend_mock_mode and value["role"] == "GUEST":
        fail(401, "AUTH_REQUIRED", "분석 결과를 저장하려면 회원가입 또는 로그인이 필요합니다.")
    try:
        run, created = create_run(
            value,
            body.category,
            body.question,
            idempotency_key.strip(),
            save_selected=body.save_selected,
            conversation_id=body.conversation_id,
        )
    except ValueError:
        fail(409, "IDEMPOTENCY_CONFLICT", "같은 Idempotency-Key에는 동일한 요청 본문만 사용할 수 있습니다.")
    if created:
        start_run(run["run_id"])
    return {"run_id": run["run_id"], "status": run["status"]}


@router.get("/agent-runs/{run_id}", summary="Agent 실행 상태 조회", description="SSE가 끊겼을 때에도 이 API로 최종 결과를 복구할 수 있습니다.")
def get_agent_run(run_id: str, value: dict = Depends(actor)) -> dict:
    return public_run(get_run(run_id, value))


@router.post("/agent-runs/{run_id}/save", summary="완료된 Agent 분석 결과 저장")
async def save_agent_run(run_id: str, value: dict = Depends(require_user)) -> dict:
    run = get_run_for_save(run_id, value)
    try:
        conversation_id = await saved_conversation_service.save_run(value, run)
    except ValueError:
        fail(409, "RUN_NOT_FINISHED", "완료되거나 보완 질문 상태인 분석 결과만 저장할 수 있습니다.")
    except SavedConversationNotFoundError:
        fail(404, "NOT_FOUND", "저장할 분석 결과를 찾을 수 없습니다.")
    except Exception:
        fail(503, "SAVED_CONVERSATION_UNAVAILABLE", "분석 결과를 저장할 수 없습니다.")
    return {"conversation_id": conversation_id, "saved": True}


def sse_event(item: dict) -> str:
    return f"id: {item['id']}\nevent: {item['event']}\ndata: {json.dumps(item['data'], ensure_ascii=False)}\n\n"


@router.get("/agent-runs/{run_id}/events", summary="Agent 분석 진행 SSE", description="Last-Event-ID 이후의 실제 Tool 실행 이벤트를 text/event-stream으로 재전송합니다.")
async def get_agent_run_events(run_id: str, last_event_id: str | None = Header(default=None, alias="Last-Event-ID"), value: dict = Depends(actor)) -> StreamingResponse:
    run = get_run(run_id, value)
    try:
        last_id = int(last_event_id or 0)
        if last_id < 0:
            raise ValueError
    except ValueError:
        fail(422, "VALIDATION_ERROR", "Last-Event-ID는 0 이상의 정수여야 합니다.")

    async def event_stream():
        sent_id = last_id
        while True:
            pending = [item for item in run["events"] if item["id"] > sent_id]
            for item in pending:
                sent_id = item["id"]
                yield sse_event(item)
            if run["status"] in {"completed", "stopped", "failed"}:
                return
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                return
            yield ": heartbeat\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/history", summary="내 질의 이력 조회", description="회원은 자신의 계정 이력, 비회원은 같은 X-Guest-Id의 이력만 볼 수 있습니다.")
def history(value: dict = Depends(actor), page_number: int = Query(1, alias="page", ge=1), page_size: int = Query(10, ge=1, le=50), type: Literal["all", "legal_analysis", "user_question"] = "all", category: Category | None = None) -> dict:
    items = [item for item in store.history.get(value["id"], []) if (type == "all" or item["type"] == type) and (not category or item["category"] == category)]
    return page(sorted(items, key=lambda item: item["created_at"], reverse=True), page_number, page_size)


@router.get("/history/{history_id}")
def history_detail(history_id: str, value: dict = Depends(actor)) -> dict:
    item = next((row for row in store.history.get(value["id"], []) if row["id"] == history_id), None)
    if not item: fail(404, "NOT_FOUND", "이력을 찾을 수 없습니다.")
    return item


@router.delete("/history/{history_id}", status_code=204)
def delete_history(history_id: str, value: dict = Depends(actor)) -> None:
    items = store.history.get(value["id"], [])
    if not any(row["id"] == history_id for row in items): fail(404, "NOT_FOUND", "이력을 찾을 수 없습니다.")
    store.history[value["id"]] = [row for row in items if row["id"] != history_id]


@router.get("/saved-conversations", summary="회원 저장 분석 목록")
async def saved_conversations(
    value: dict = Depends(require_user),
    page_number: int = Query(1, alias="page", ge=1),
    page_size: int = Query(20, alias="page_size", ge=1, le=50),
) -> dict:
    try:
        items, total = await saved_conversation_service.list_history_for_actor(
            actor=value, page=page_number, page_size=page_size,
        )
        return {"items": items, "page": page_number, "page_size": page_size, "total": total}
    except Exception as error:
        if isinstance(error, PermissionError):
            fail(401, "AUTH_REQUIRED", "저장 분석은 로그인 후 사용할 수 있습니다.")
        fail(503, "SAVED_CONVERSATION_UNAVAILABLE", "저장 분석을 불러올 수 없습니다.")


@router.get("/saved-conversations/{conversation_id}", summary="회원 저장 분석 복원")
async def saved_conversation_detail(conversation_id: int, value: dict = Depends(require_user)) -> dict:
    try:
        return await saved_conversation_service.restore_history_for_actor(value, conversation_id)
    except SavedConversationNotFoundError:
        fail(404, "NOT_FOUND", "저장 분석을 찾을 수 없습니다.")
    except Exception:
        fail(503, "SAVED_CONVERSATION_UNAVAILABLE", "저장 분석을 불러올 수 없습니다.")


@router.delete("/saved-conversations/{conversation_id}", status_code=204, summary="회원 저장 분석 삭제")
async def delete_saved_conversation(conversation_id: int, value: dict = Depends(require_user)) -> None:
    try:
        await saved_conversation_service.delete_for_actor(value, conversation_id)
    except SavedConversationNotFoundError:
        fail(404, "NOT_FOUND", "저장 분석을 찾을 수 없습니다.")
    except Exception:
        fail(503, "SAVED_CONVERSATION_UNAVAILABLE", "저장 분석을 삭제할 수 없습니다.")


def guest_history_item(record: dict) -> dict:
    item_type = "legal_terms" if record.get("kind") == "legal_term_chat" else "analysis"
    result = record.get("result") or {}
    item = {
        "id": record["run_id"],
        "type": item_type,
        "title": record.get("question", "")[:100],
        "question": record.get("question", ""),
        "summary": "용어 설명" if item_type == "legal_terms" else result.get("question_summary", result.get("answer", ""))[:300],
        "created_at": record.get("updated_at") or datetime.now(timezone.utc).isoformat(),
    }
    if item_type == "legal_terms":
        item["messages"] = [
            {"role": "user", "content": record.get("question", "")},
            {"role": "assistant", "content": result.get("answer", "")},
        ]
    else:
        item["result"] = result
    return item


@router.get("/guest/temporary-history", summary="비회원 임시 분석 이력")
async def guest_temporary_history(value: dict = Depends(actor)) -> dict:
    if value["role"] != "GUEST":
        fail(409, "MEMBER_SESSION", "회원 저장 분석은 /saved-conversations를 사용하세요.")
    try:
        items, expires_in = await guest_sessions.list_analyses(str(value["id"]))
    except SessionStoreUnavailableError:
        fail(503, "GUEST_SESSION_UNAVAILABLE", "비회원 임시 이력을 불러올 수 없습니다.")
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()
    return {
        "items": [guest_history_item(item) for item in items],
        "expires_at": expires_at,
        "expires_in": expires_in,
        "notice": "비회원 분석 이력은 임시 보관되며, 시간이 지나거나 서버가 재시작되면 삭제될 수 있습니다.",
    }


@router.delete("/guest/temporary-history", status_code=204, summary="비회원 임시 분석 이력 삭제")
async def clear_guest_temporary_history(value: dict = Depends(actor)) -> None:
    if value["role"] != "GUEST":
        fail(409, "MEMBER_SESSION", "회원 저장 분석은 /saved-conversations를 사용하세요.")
    try:
        await guest_sessions.clear(str(value["id"]))
    except SessionStoreUnavailableError:
        fail(503, "GUEST_SESSION_UNAVAILABLE", "비회원 임시 이력을 삭제할 수 없습니다.")


@router.get("/notifications", summary="내 알림 목록", description="미읽음 알림이 먼저 나오고, 같은 상태에서는 최신 알림이 먼저 나옵니다.")
def notifications(value: dict = Depends(actor), page_number: int = Query(1, alias="page", ge=1), page_size: int = Query(20, ge=1, le=50)) -> dict:
    items = sorted(store.notifications.get(value["id"], []), key=lambda item: (item["is_read"], item["created_at"]), reverse=False)
    return page(items, page_number, page_size)


@router.get("/notifications/unread-count")
def unread(value: dict = Depends(actor)) -> dict:
    return {"count": sum(not item["is_read"] for item in store.notifications.get(value["id"], []))}


@router.patch("/notifications/{notification_id}/read")
def read_notification(notification_id: str, value: dict = Depends(actor)) -> dict:
    item = next((row for row in store.notifications.get(value["id"], []) if row["id"] == notification_id), None)
    if not item: fail(404, "NOT_FOUND", "알림을 찾을 수 없습니다.")
    item["is_read"] = True; return item


@router.patch("/notifications/read-all")
def read_all(value: dict = Depends(actor)) -> dict:
    for item in store.notifications.get(value["id"], []): item["is_read"] = True
    return {"updated": True}


@router.delete("/notifications/read-items", status_code=204, summary="읽은 알림 일괄 삭제", description="현재 사용자에게 속한 읽은 알림만 모두 삭제합니다.")
def delete_read_items(value: dict = Depends(actor)) -> None:
    store.notifications[value["id"]] = [item for item in store.notifications.get(value["id"], []) if not item["is_read"]]


@router.delete("/notifications/{notification_id}", status_code=204)
def delete_notification(notification_id: str, value: dict = Depends(actor)) -> None:
    items = store.notifications.get(value["id"], [])
    if not any(item["id"] == notification_id for item in items): fail(404, "NOT_FOUND", "알림을 찾을 수 없습니다.")
    store.notifications[value["id"]] = [item for item in items if item["id"] != notification_id]
