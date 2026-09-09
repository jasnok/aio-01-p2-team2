import asyncio

from backend.app.schemas.legal import (
    Evidence,
    LegalQuestionResponse,
)
from backend.app.services.conversation_service import (
    ConversationService,
)


class FakeConversationRepository:
    def __init__(self) -> None:
        self.sources: list[dict] = []

    async def get_or_create_user_id(self, actor_key: str) -> int:
        assert actor_key == "guest:test-user"
        return 10

    async def create_conversation(
        self,
        *,
        user_id: int,
        title: str,
        source_request_id: str,
    ) -> dict:
        assert user_id == 10
        assert source_request_id.startswith("req-test-")

        return {"id": 100}

    async def create_message(
        self,
        *,
        conversation_id: int,
        role: str,
        content: str,
    ) -> dict:
        assert conversation_id == 100

        if role == "user":
            return {"id": 200}

        return {"id": 201}

    async def create_message_source(self, **kwargs) -> dict:
        self.sources.append(kwargs)
        return {"id": 300}

    async def get_first_user_message(
        self,
        *,
        conversation_id: int,
        user_id: int,
    ) -> dict:
        assert conversation_id == 100
        assert user_id == 10

        return {
            "id": 1,
            "role": "user",
            "content": "처음 보증금 반환 문제를 질문했습니다.",
        }

    async def get_recent_messages(
        self,
        *,
        conversation_id: int,
        user_id: int,
        limit: int,
    ) -> list[dict]:
        assert conversation_id == 100
        assert user_id == 10
        assert limit == 3

        return [
            {
                "id": 1,
                "role": "user",
                "content": "처음 보증금 반환 문제를 질문했습니다.",
            },
            {
                "id": 2,
                "role": "assistant",
                "content": "계약 종료일과 목적물 인도 여부를 확인해 주세요.",
            },
            {
                "id": 3,
                "role": "user",
                "content": "계약은 끝났고 집도 인도했습니다.",
            },
        ]
    async def find_user_id(
        self,
        *,
        actor_key: str,
    ) -> int | None:
        if actor_key == "guest:test-user":
            return 10
        return None

    async def get_conversation_for_user(
        self,
        *,
        conversation_id: int,
        user_id: int,
    ) -> dict | None:
        if conversation_id == 100 and user_id == 10:
            return {
                "id": 100,
                "user_id": 10,
                "title": "보증금 반환 질문",
                "source_request_id": "req-test-001",
            }
        return None

    


class FailIfCalledRepository:
    def __getattr__(self, name: str):
        raise AssertionError(
            f"저장 미선택인데 Repository가 호출되었습니다: {name}"
        )


def test_save_completed_analysis_saves_question_answer_and_source() -> None:
    repository = FakeConversationRepository()
    service = ConversationService(repository)

    evidence = Evidence(
        evidence_id="law-101",
        document_id="101",
        title="주택임대차보호법",
        content="보증금 반환 관련 조문",
        source={
            "source_id": "101",
            "title": "국가법령정보센터",
            "source_type": "law",
            "url": "https://example.com/law-101",
        },
        metadata={"chunk_id": "5"},
    )

    result = asyncio.run(
        service.save_completed_analysis(
            actor_key="guest:test-user",
            request_id="req-test-001",
            question="보증금을 돌려받지 못했습니다.",
            answer="관련 법령을 확인해 보세요.",
            evidence_items=[evidence],
        )
    )

    assert result["conversation_id"] == 100
    assert result["user_message_id"] == 200
    assert result["assistant_message_id"] == 201

    assert repository.sources == [
        {
            "message_id": 201,
            "document_id": 101,
            "chunk_id": 5,
            "source_url": "https://example.com/law-101",
        }
    ]

def make_evidence(
    evidence_id: str,
    source_type: str,
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        document_id="101",
        title=f"{source_type} 자료",
        content="테스트 근거",
        source={
            "source_id": evidence_id,
            "title": "테스트 출처",
            "source_type": source_type,
            "url": f"https://example.com/{evidence_id}",
        },
    )


def test_save_analysis_response_collects_all_evidence_types() -> None:
    repository = FakeConversationRepository()
    service = ConversationService(repository)

    response = LegalQuestionResponse(
        request_id="req-test-002",
        agent_id="housing",
        termination_reason="model_finished",
        question_summary="보증금 반환",
        answer="검색 결과입니다.",
        related_laws=[make_evidence("law-1", "law")],
        similar_cases=[make_evidence("case-1", "case")],
        consultations=[make_evidence("consultation-1", "consultation")],
        is_mock=False,
    )

    asyncio.run(
        service.save_analysis_response(
            actor_key="guest:test-user",
            question="보증금을 돌려받지 못했습니다.",
            response=response,
        )
    )

    assert len(repository.sources) == 3
    assert {
        item["source_url"]
        for item in repository.sources
    } == {
        "https://example.com/law-1",
        "https://example.com/case-1",
        "https://example.com/consultation-1",
    }

def test_build_context_keeps_first_and_recent_messages() -> None:
    service = ConversationService(FakeConversationRepository())

    context = asyncio.run(
        service.build_context(
            conversation_id=100,
            user_id=10,
            max_characters=3000,
        )
    )

    assert [message["id"] for message in context] == [1, 2, 3]
    assert context[0]["content"] == "처음 보증금 반환 문제를 질문했습니다."
    assert context[-1]["content"] == "계약은 끝났고 집도 인도했습니다."

def test_save_if_not_selected_does_not_write_to_database() -> None:
    service = ConversationService(FailIfCalledRepository())

    response = LegalQuestionResponse(
        request_id="req-test-003",
        agent_id="housing",
        termination_reason="model_finished",
        question_summary="보증금 반환",
        answer="검색 결과입니다.",
        is_mock=False,
    )

    result = asyncio.run(
        service.save_if_selected(
            save_selected=False,
            actor_key="guest:test-user",
            question="보증금을 돌려받지 못했습니다.",
            response=response,
        )
    )

    assert result is None

def test_save_if_selected_saves_analysis() -> None:
    repository = FakeConversationRepository()
    service = ConversationService(repository)

    response = LegalQuestionResponse(
        request_id="req-test-004",
        agent_id="housing",
        termination_reason="model_finished",
        question_summary="보증금 반환",
        answer="검색 결과입니다.",
        related_laws=[make_evidence("101", "law")],
        is_mock=False,
    )

    result = asyncio.run(
        service.save_if_selected(
            save_selected=True,
            actor_key="guest:test-user",
            question="보증금을 돌려받지 못했습니다.",
            response=response,
        )
    )

    assert result["conversation_id"] == 100
    assert result["user_message_id"] == 200
    assert result["assistant_message_id"] == 201
    assert repository.sources[0]["message_id"] == 201

def test_get_conversation_for_actor_checks_ownership() -> None:
    service = ConversationService(FakeConversationRepository())

    own_conversation = asyncio.run(
        service.get_conversation_for_actor(
            conversation_id=100,
            actor_key="guest:test-user",
        )
    )

    other_conversation = asyncio.run(
        service.get_conversation_for_actor(
            conversation_id=100,
            actor_key="guest:other-user",
        )
    )

    assert own_conversation is not None
    assert own_conversation["id"] == 100
    assert other_conversation is None