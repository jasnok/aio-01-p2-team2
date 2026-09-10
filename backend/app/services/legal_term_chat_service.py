from __future__ import annotations

import asyncio
import json
import logging
from uuid import uuid4

from backend.app.core.config import get_settings
from backend.app.providers.registry import get_provider
from backend.app.schemas.legal_terms import LegalTermChatResponse, LegalTermLLMOutput


logger = logging.getLogger(__name__)

TERM_PERSONA = """
당신은 일반 시민에게 법률 용어와 제도를 쉬운 한국어로 설명하는 도우미입니다.
법률 용어, 제도, 일반 절차만 설명하고 개별 사건의 승소 가능성, 처벌, 계약 효력처럼
구체적인 법률 판단은 하지 마세요. 쉬운 말로 3~6문장 안에서 설명하고, 필요하면 짧은
예시를 하나만 드세요. 법률 용어 질문이 아니면 is_legal_term_question을 false로 설정하고
법률 용어 또는 제도에 관한 질문을 요청하세요. 개인정보를 요구하지 마세요.
""".strip()
NOTICE = "일반적인 법률 용어 설명이며, 개별 사안에 대한 법률 자문이나 결론은 아닙니다."


class LegalTermChatService:
    async def chat(self, message: str, context: list[dict[str, str]]) -> LegalTermChatResponse:
        request_id = f"term-{uuid4()}"
        settings = get_settings()
        if settings.llm_provider == "mock":
            return LegalTermChatResponse(
                request_id=request_id,
                answer="법률 용어 대화 기능을 사용하려면 실제 LLM Provider 설정이 필요합니다.",
                notice=NOTICE, storage="none", is_llm_response=False,
            )
        payload = json.dumps({
            "conversation_context": context,
            "message": message,
        }, ensure_ascii=False)
        try:
            provider = get_provider(settings.llm_provider)
            result = await asyncio.to_thread(
                provider.generate_structured, TERM_PERSONA, payload, LegalTermLLMOutput,
            )
            output = LegalTermLLMOutput.model_validate(result.output)
        except Exception:
            logger.exception("legal_term_chat_failed")
            raise RuntimeError("LLM_UNAVAILABLE")
        if not output.is_legal_term_question:
            output = LegalTermLLMOutput(
                is_legal_term_question=False,
                answer="법률 용어 또는 제도에 관한 질문을 해 주세요. 예: ‘임금체불이 무슨 뜻인가요?’",
                caution=NOTICE,
            )
        return LegalTermChatResponse(
            request_id=request_id, answer=output.answer,
            related_terms=output.related_terms, notice=output.caution or NOTICE,
            storage="none", is_llm_response=True,
        )
