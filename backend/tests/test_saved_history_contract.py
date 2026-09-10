import asyncio
from datetime import datetime, timezone

from backend.app.routers.mock_api import guest_history_item
from backend.app.services.saved_conversation_service import SavedConversationService


def test_history_list_item_matches_frontend_type_contract() -> None:
    item = SavedConversationService._history_item({
        "id": 11, "title": "퇴직금", "category": "labor", "question": "퇴직금 질문",
        "answer": "답변", "created_at": datetime.now(timezone.utc),
        "assistant_snapshot": {"version": 1, "payload": {
            "question_summary": "퇴직금 미지급 관련 설명", "answer": "답변",
        }},
    })

    assert item["id"] == 11
    assert item["type"] == "analysis"
    assert item["question"] == "퇴직금 질문"
    assert item["summary"] == "퇴직금 미지급 관련 설명"


def test_history_snapshot_json_string_is_restored() -> None:
    item = SavedConversationService._history_item({
        "id": 12, "title": "분석", "category": "labor", "question": "질문",
        "answer": "답변", "created_at": datetime.now(timezone.utc),
        "assistant_snapshot": '{"version": 1, "payload": {"question_summary": "요약"}}',
    })
    assert item["summary"] == "요약"


def test_term_history_detail_returns_messages_and_analysis_detail_returns_result() -> None:
    class Repository:
        async def restore(self, user_id, conversation_id):
            if conversation_id == 1:
                return {
                    "conversation": {"id": 1, "title": "용어", "category": "legal_terms", "created_at": datetime.now(timezone.utc)},
                    "messages": [
                        {"role": "user", "content": "임금체불", "created_at": datetime.now(timezone.utc)},
                        {"role": "assistant", "content": "설명", "snapshot": {"version": 1, "payload": {"answer": "설명"}}, "created_at": datetime.now(timezone.utc)},
                    ],
                }
            return {
                "conversation": {"id": 2, "title": "분석", "category": "labor", "created_at": datetime.now(timezone.utc)},
                "messages": [
                    {"role": "user", "content": "질문", "created_at": datetime.now(timezone.utc)},
                    {"role": "assistant", "content": "답변", "snapshot": {"version": 1, "payload": {"answer": "답변", "agent_id": "labor"}}, "created_at": datetime.now(timezone.utc)},
                ],
            }

    service = SavedConversationService(Repository())
    term = asyncio.run(service.restore_history_for_actor({"id": 42, "role": "USER"}, 1))
    analysis = asyncio.run(service.restore_history_for_actor({"id": 42, "role": "USER"}, 2))

    assert term["type"] == "legal_terms"
    assert term["messages"][1]["content"] == "설명"
    assert analysis["type"] == "analysis"
    assert analysis["result"]["agent_id"] == "labor"


def test_guest_history_contains_type_and_type_specific_detail() -> None:
    term = guest_history_item({
        "kind": "legal_term_chat", "run_id": "term-1", "question": "임금체불",
        "result": {"answer": "설명"}, "updated_at": "2026-09-09T00:00:00+00:00",
    })
    analysis = guest_history_item({
        "kind": "legal_analysis", "run_id": "run-1", "question": "퇴직금",
        "result": {"answer": "분석 답변"}, "updated_at": "2026-09-09T00:00:00+00:00",
    })

    assert term["type"] == "legal_terms" and term["messages"][1]["content"] == "설명"
    assert analysis["type"] == "analysis" and analysis["result"]["answer"] == "분석 답변"
