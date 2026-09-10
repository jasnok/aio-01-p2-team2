import pytest
from streamlit.testing.v1 import AppTest


@pytest.mark.parametrize("count", [0, 1, 3])
def test_collapsed_sections_contain_collapsed_details(count):
    fields = ("related_laws", "similar_cases", "consultations")
    headings = ("관련 법령", "유사 판례", "소비자원 상담사례")
    result = dict(answer="안내", is_mock=False, follow_up_questions=["추가 질문"])
    for field in fields:
        result[field] = [dict(title=f"자료 {i}", content="긴 본문 " * 100) for i in range(count)]
    app = AppTest.from_string(
        "from frontend.components.answer_view import render_analysis_result\n"
        f"render_analysis_result({ascii(result)})"
    ).run(timeout=20)
    assert not app.exception
    assert not app.toggle
    assert app.get("download_button")
    for heading in headings:
        section = next(e for e in app.expander if e.label == f"{heading} ({count}건)")
        assert not section.proto.expanded
        details = [e for e in section.expander if e.label == "상세보기"]
        assert len(details) == count
        assert all(not e.proto.expanded for e in details)
        if not count:
            assert any("표시할 자료가 없습니다" in e.value for e in section.markdown)
    app.run(timeout=20)
    assert not app.exception
