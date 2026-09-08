import pytest
from streamlit.testing.v1 import AppTest
from frontend.components.stream_analysis import friendly_event


@pytest.mark.parametrize("kind", ["law", "case", "consultation"])
def test_unified_card_preview_and_full_detail(kind):
    body = "본문 내용 " * 80
    item = {"title": "제목", "content": body, "source": {"title": "기관", "url": "https://example.test"}}
    app = AppTest.from_string(
        "from frontend.components.evidence_card import render_evidence_card\n"
        f"render_evidence_card({ascii(item)}, 1, {kind!r})"
    ).run()
    assert not app.exception
    assert len(app.expander) == 1
    assert app.expander[0].label == "상세보기"
    assert any(x.value == body.strip() for x in app.expander[0].markdown)
    assert not app.get("link_button")
    preview = [x.value for x in app.markdown if x.value.endswith("…")]
    assert len(preview) == 1 and len(preview[0]) == 150


def test_sse_messages_never_echo_internal_message():
    for event in ["step.started", "step.completed", "run.started", "run.failed", "run.completed"]:
        text = friendly_event(event, {"tool": "search_laws", "message": "secret_tool_name", "result_count": 3})
        assert "search_laws" not in text and "secret_tool_name" not in text
    assert "3건" in friendly_event("step.completed", {"tool": "search_cases", "result_count": 3})
