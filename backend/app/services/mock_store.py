"""In-memory implementation used only while BACKEND_MOCK_MODE is enabled.

The public routers deliberately depend on this small repository instead of on
Streamlit state.  Replacing this module with PostgreSQL/Redis later therefore
does not change the HTTP contract.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4


class SessionExpiredError(PermissionError):
    """만료된 Token과 Token 누락을 API 응답에서 구분한다."""


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime | None = None) -> str:
    return (value or now()).isoformat()


def hash_password(password: str) -> str:
    """Use a salted, deliberately expensive standard-library password hash."""
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return "scrypt$" + base64.b64encode(salt + digest).decode()


def verify_password(password: str, stored: str | None) -> bool:
    if not stored or not stored.startswith("scrypt$"):
        return False
    try:
        payload = base64.b64decode(stored.split("$", 1)[1])
        salt, digest = payload[:16], payload[16:]
        candidate = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
        return hmac.compare_digest(candidate, digest)
    except (ValueError, TypeError):
        return False


class MemoryStore:
    def __init__(self) -> None:
        self.users: dict[str, dict] = {}
        self.sessions: dict[str, dict] = {}
        self.questions: dict[str, dict] = {}
        self.comments: dict[str, dict] = {}
        self.faqs: dict[str, dict] = {}
        self.notifications: dict[str, list[dict]] = {}
        self.history: dict[str, list[dict]] = {}
        self.unlocks: dict[tuple[str, str], datetime] = {}
        self.idempotency: dict[tuple[str, str, str], tuple[datetime, dict]] = {}
        self.agent_runs: dict[str, dict] = {}
        self.audit_logs: list[dict] = []
        self._seed()

    def _seed(self) -> None:
        for email, name, role, password in [
            ("user@lawpath.demo", "법률초보", "USER", "Demo1234!"),
            ("admin@lawpath.demo", "관리자", "ADMIN", "Admin1234!"),
        ]:
            user_id = f"{role.lower()}-demo"
            self.users[user_id] = {"id": user_id, "email": email, "display_name": name, "role": role, "password_hash": hash_password(password)}
        for category, question, answer, pinned, order in [
            ("housing", "계약이 끝나면 보증금은 언제 반환하나요?", "계약과 사실관계에 따라 달라질 수 있어 공식 자료 확인이 필요합니다.", True, 1),
            ("housing", "내용증명을 꼭 보내야 하나요?", "요청 사실을 남기는 방법으로 검토할 수 있습니다.", False, 2),
            ("labor", "퇴직금 요건은 무엇인가요?", "근로기간과 근로형태 등 구체적인 사실을 확인해야 합니다.", True, 3),
            ("consumer", "중고거래도 환불할 수 있나요?", "거래 조건과 상품 상태를 함께 확인해야 합니다.", False, 4),
        ]:
            faq_id = f"faq-{uuid4()}"
            self.faqs[faq_id] = {"id": faq_id, "category": category, "question": question, "answer": answer, "is_active": True, "is_pinned": pinned, "display_order": order, "updated_at": iso()}

    def public_user(self, user: dict) -> dict:
        return {key: user[key] for key in ("id", "role", "display_name")}

    def owner_key(self, actor: dict) -> str:
        return actor["id"]

    def issue_session(self, user: dict) -> tuple[str, dict]:
        token = secrets.token_urlsafe(32)
        self.sessions[token] = {"user_id": user["id"], "expires_at": now() + timedelta(hours=8)}
        return token, self.public_user(user)

    def actor_for_token(self, token: str | None, guest_id: str | None) -> dict:
        if token:
            session = self.sessions.get(token)
            if not session:
                raise PermissionError("AUTH_REQUIRED")
            if session["expires_at"] <= now():
                self.sessions.pop(token, None)
                raise SessionExpiredError("AUTH_SESSION_EXPIRED")
            return self.public_user(self.users[session["user_id"]])
        return {"id": guest_id or "guest-anonymous", "role": "GUEST", "display_name": "비회원"}

    def notify(self, owner_id: str, kind: str, title: str, message: str, *, target_type: str | None = None, target_id: str | None = None, category: str | None = None, severity: str = "info") -> None:
        item = {"id": f"notification-{uuid4()}", "type": kind, "title": title, "message": message, "severity": severity, "target_type": target_type, "target_id": target_id, "category": category, "created_at": iso(), "is_read": False}
        self.notifications.setdefault(owner_id, []).append(item)

    def audit(self, actor: dict, action: str, target_id: str, reason: str | None = None) -> None:
        self.audit_logs.append({"id": str(uuid4()), "actor_id": actor["id"], "action": action, "target_id": target_id, "reason": reason, "created_at": iso()})


store = MemoryStore()
