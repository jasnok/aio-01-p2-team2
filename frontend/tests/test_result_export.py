from frontend.components.result_export import build_analysis_markdown


def test_build_analysis_markdown_contains_user_visible_sections() -> None:
    result = {
        "agent_id": "housing",
        "question": "보증금을 돌려받지 못했습니다.",
        "question_summary": "보증금 반환 상황",
        "key_issues": ["계약 종료"],
        "answer": "자료를 정리하세요.",
        "related_laws": [{"title": "법령 예시", "article": "제1조", "summary": "요약"}],
        "similar_cases": [{"title": "판례 예시", "case_number": "DEMO-1", "date": "2024-01-01", "result": "예시 결과"}],
    }

    markdown = build_analysis_markdown(result)

    assert "# LawPath 사례 분석 결과" in markdown
    assert "보증금을 돌려받지 못했습니다." in markdown
    assert "법령 예시" in markdown
    assert "판례 예시" in markdown
    assert "법률 자문이나 판결 예측이 아닙니다" in markdown
