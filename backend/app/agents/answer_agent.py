from backend.app.agents.models import AnswerDraft
from backend.app.schemas.legal import Evidence


class AnswerAgent:
    def _titles_for(
        self,
        evidence: list[Evidence],
        source_type: str,
    ) -> list[str]:
        return [
            item.title
            for item in evidence
            if item.source.source_type == source_type
        ]

    def create_draft(
        self,
        category: str,
        question: str,
        evidence: list[Evidence],
    ) -> AnswerDraft:
        if not evidence:
            return AnswerDraft(
                question_summary="검색 결과가 없습니다.",
                answer="현재 입력한 내용과 관련된 공식 근거를 찾지 못했습니다.",
                cautions=[
                    "검색 결과가 없을 때는 추측으로 답변하지 않습니다.",
                    "사실관계나 검색어를 보완해 다시 확인해 주세요.",
                ],
            )

        law_titles = self._titles_for(evidence, "law")
        consultation_titles = self._titles_for(evidence, "consultation")
        case_titles = self._titles_for(evidence, "case")

        return AnswerDraft(
            question_summary=f"{category} 분야의 공식 검색 근거를 확인했습니다.",
            answer=(
                "검색된 공식 자료를 기준으로 확인할 사항을 정리했습니다. "
                f"법령 {len(law_titles)}건: {', '.join(law_titles) or '없음'}. "
                f"상담사례 {len(consultation_titles)}건: {', '.join(consultation_titles) or '없음'}. "
                f"판례 {len(case_titles)}건: {', '.join(case_titles) or '없음'}. "
                "각 출처의 원문과 구체적인 사실관계를 함께 확인해 주세요."
            ),
            key_issues=[
                "사용자가 입력한 사실관계",
                "검색된 공식 근거",
                "출처 원문 확인",
            ],
            cautions=[
                "검색 결과는 법률 자문이나 결과 보장이 아닙니다.",
                "검색 근거에 없는 내용을 추가로 단정하지 않습니다.",
            ],
            used_evidence_ids=[item.evidence_id for item in evidence],
        )
