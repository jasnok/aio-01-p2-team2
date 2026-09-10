from datetime import datetime, timezone

from pydantic import ValidationError

from frontend.clients import backend_client as api
from frontend.core.storage_models import HistoryItemView, HistoryPageView


def normalize_item(payload, kind):
    if not isinstance(payload, dict):
        raise ValueError("Invalid history item")
    data = dict(payload)
    data.setdefault("id", data.get("conversation_id", data.get("request_id")))
    # Endpoint identity determines deletion routing, never a display label.
    data["type"] = kind
    data.setdefault("summary", data.get("question_summary") or "")
    if "result" not in data and all(k in data for k in ("agent_id", "answer", "status", "termination_reason", "request_id")):
        data["result"] = payload
    return HistoryItemView.model_validate(data).model_dump(mode="json")


def parse_page(payload, kind=None):
    try:
        if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
            raise ValueError("Missing items")
        items = []
        for item in payload["items"]:
            item_kind = kind or item.get("type")
            if item_kind not in ("analysis", "legal_terms"):
                raise ValueError("Missing guest history type")
            items.append(normalize_item(item, item_kind))
        page = HistoryPageView.model_validate({**payload, "items": items}).model_dump(mode="json")
        page["items"] = [item for item in page["items"] if not is_expired(item)]
        return page
    except (ValidationError, ValueError, TypeError, AttributeError) as error:
        raise api.BackendClientError("이력 응답 형식이 계약과 다릅니다. 서버 연동 확인이 필요합니다.", "CONTRACT_MISMATCH") from error


def is_expired(item):
    if not item.get("expires_at"):
        return False
    expiry = datetime.fromisoformat(item["expires_at"].replace("Z", "+00:00"))
    if expiry.tzinfo is None:
        # A timezone-less timestamp cannot establish expiration safely.
        return False
    return expiry <= datetime.now(timezone.utc)


def load_detail(token, item):
    kind = item["type"]
    if kind == "analysis":
        payload = api.get_saved_conversation(token, item["id"])
    else:
        payload = api.get_legal_term_conversation(token, item["id"])
    try:
        detail = normalize_item({**item, **payload}, kind)
        if str(detail["id"]) != str(item["id"]):
            raise ValueError("Mismatched ID")
        return detail
    except (ValidationError, ValueError, TypeError) as error:
        raise api.BackendClientError("이력 상세 응답 형식을 확인할 수 없습니다.", "CONTRACT_MISMATCH") from error
