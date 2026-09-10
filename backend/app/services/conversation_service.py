from backend.app.schemas.legal import (
    Evidence,
    LegalQuestionResponse,
)

from backend.app.repositories.conversation_repository import (
    ConversationRepository,
)


class ConversationService:
    def __init__(
        self,
        repository: ConversationRepository | None = None,
    ) -> None:
        self.repository = repository or ConversationRepository()

    @staticmethod
    def _to_int_or_none(value: object) -> int | None:
        try:
            return int(str(value))
        except (TypeError, ValueError):
            return None

    async def save_answer_sources(
        self,
        *,
        message_id: int,
        evidence_items: list[Evidence],
        ) -> None:
        for evidence in evidence_items:
            document_id = self._to_int_or_none(
                evidence.document_id
            )
            chunk_id = self._to_int_or_none(
                evidence.metadata.get("chunk_id")
            )

            await self.repository.create_message_source(
                message_id=message_id,
                document_id=document_id,
                chunk_id=chunk_id,
                source_url=evidence.source.url,
            )

    async def save_completed_analysis(
        self,
        *,
        actor_key: str,
        request_id: str,
        question: str,
        answer: str,
        evidence_items: list[Evidence],
        conversation_id: int | None = None,
    ) -> dict:
        user_id = await self.repository.get_or_create_user_id(
            actor_key
        )

        if conversation_id is None:
            conversation = await self.repository.create_conversation(
                user_id=user_id,
                title=question[:80],
                source_request_id=request_id,
            )
        else:
            conversation = await self.repository.get_conversation_for_user(
                conversation_id=conversation_id,
                user_id=user_id,
            )
            if conversation is None:
                raise PermissionError("conversation is not owned by actor")

        user_message = await self.repository.create_message(
            conversation_id=conversation["id"],
            role="user",
            content=question,
        )

        assistant_message = await self.repository.create_message(
            conversation_id=conversation["id"],
            role="assistant",
            content=answer,
        )

        await self.save_answer_sources(
            message_id=assistant_message["id"],
            evidence_items=evidence_items,
        )

        return {
            "conversation_id": conversation["id"],
            "user_message_id": user_message["id"],
            "assistant_message_id": assistant_message["id"],
        }
    
    async def save_analysis_response(
        self,
        *,
        actor_key: str,
        question: str,
        response: LegalQuestionResponse,
        conversation_id: int | None = None,
    ) -> dict:
        evidence_items = [
            *response.related_laws,
            *response.similar_cases,
            *response.consultations,
        ]

        return await self.save_completed_analysis(
            actor_key=actor_key,
            request_id=response.request_id,
            question=question,
            answer=response.answer,
            evidence_items=evidence_items,
            conversation_id=conversation_id,
        )

    async def build_context(
        self,
        *,
        conversation_id: int,
        user_id: int,
        max_characters: int = 3000,
    ) -> list[dict]:
        first_message = await self.repository.get_first_user_message(
            conversation_id=conversation_id,
            user_id=user_id,
        )

        recent_messages = await self.repository.get_recent_messages(
            conversation_id=conversation_id,
            user_id=user_id,
            limit=3,
        )

        context_messages: list[dict] = []

        if first_message is not None:
            context_messages.append(first_message)

        for message in recent_messages:
            if first_message and message["id"] == first_message["id"]:
                continue

            context_messages.append(message)

        trimmed_messages: list[dict] = []
        remaining = max_characters

        for message in context_messages:
            content = message["content"]

            if remaining <= 0:
                break

            if len(content) > remaining:
                message = {
                    **message,
                    "content": content[:remaining],
                }

            trimmed_messages.append(message)
            remaining -= len(message["content"])

        return trimmed_messages

    async def save_if_selected(
        self,
        *,
        save_selected: bool,
        actor_key: str,
        question: str,
        response: LegalQuestionResponse,
        conversation_id: int | None = None,
    ) -> dict | None:
        if not save_selected:
            return None

        return await self.save_analysis_response(
            actor_key=actor_key,
            question=question,
            response=response,
            conversation_id=conversation_id,
        )

    async def get_conversation_for_actor(
        self,
        *,
        conversation_id: int,
        actor_key: str,
    ) -> dict | None:
        user_id = await self.repository.find_user_id(
            actor_key=actor_key,
        )

        if user_id is None:
            return None

        return await self.repository.get_conversation_for_user(
            conversation_id=conversation_id,
            user_id=user_id,
        )

    async def build_context_for_actor(
        self,
        *,
        conversation_id: int,
        actor_key: str,
        max_characters: int = 3000,
    ) -> list[dict]:
        conversation = await self.get_conversation_for_actor(
            conversation_id=conversation_id,
            actor_key=actor_key,
        )

        if conversation is None:
            return []

        return await self.build_context(
            conversation_id=conversation["id"],
            user_id=conversation["user_id"],
            max_characters=max_characters,
        )
