from backend.app.agents.answer_agent import AnswerAgent
from backend.app.schemas.legal import Evidence, Source


def make_evidence(
    evidence_id: str,
    source_type: str,
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id,
        document_id=evidence_id,
        title=f"{source_type} 테스트 자료",
        content="검색된 공식 근거 본문입니다.",
        source=Source(
            source_id=evidence_id,
            title="공식 출처",
            source_type=source_type,
            url="https://example.com/source",
        ),
    )


def test_answer_agent_does_not_make_up_answer_without_evidence() -> None:
    draft = AnswerAgent().create_draft(
        category="labor",
        question="퇴직금을 받지 못했습니다.",
        evidence=[],
    )

    assert draft.question_summary == "검색 결과가 없습니다."
    assert "공식 근거를 찾지 못했습니다." in draft.answer
    assert "추측" in draft.cautions[0]


def test_answer_agent_summarizes_evidence_counts() -> None:
    draft = AnswerAgent().create_draft(
        category="consumer",
        question="카드 할부 결제 물건이 배송되지 않았습니다.",
        evidence=[
            make_evidence("law-1", "law"),
            make_evidence("consultation-1", "consultation"),
            make_evidence("case-1", "case"),
        ],
    )

    assert draft.question_summary == "consumer 분야의 공식 검색 근거를 확인했습니다."
    assert "법령 1건" in draft.answer
    assert "상담사례 1건" in draft.answer
    assert "판례 1건" in draft.answer