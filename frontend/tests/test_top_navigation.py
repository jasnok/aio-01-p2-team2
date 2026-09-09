from pathlib import Path
from streamlit.testing.v1 import AppTest

APP = Path(__file__).parents[1] / "app.py"


def test_top_navigation_preserves_analysis_and_has_no_sidebar():
    app = AppTest.from_file(str(APP)).run(timeout=20)
    app.button(key="category-housing").click().run(timeout=20)
    assert not app.sidebar.button
    assert [b.key for b in app.button if (b.key or "").startswith("nav-")] == ["nav-analysis", "nav-terms", "nav-faq", "nav-history"]
    app.text_area(key="question_message").set_value("보증금 반환에 대해 질문합니다.").run()
    app.button(key="nav-faq").click().run(timeout=20)
    assert not app.exception
    app.button(key="nav-history").click().run(timeout=20)
    assert not app.exception
    app.button(key="nav-analysis").click().run(timeout=20)
    assert app.text_area(key="question_message").value == "보증금 반환에 대해 질문합니다."
    assert not app.sidebar.button


def test_source_metadata_never_rendered_or_exported():
    from frontend.components.result_export import build_analysis_markdown
    item = {"title": "제목", "content": "법률 내용", "source": {
        "title": "SECRET_SOURCE", "url": "https://hidden.test", "source_id": "secret-id"}}
    app = AppTest.from_string(
        "from frontend.components.evidence_card import render_evidence_card\n"
        f"render_evidence_card({ascii(item)}, 1, 'consultation')"
    ).run()
    visible = " ".join(x.value for x in (*app.markdown, *app.caption))
    assert "SECRET_SOURCE" not in visible
    assert "hidden.test" not in visible
    assert not app.get("link_button")
    exported = build_analysis_markdown({"consultations": [item]})
    assert "SECRET_SOURCE" not in exported and "hidden.test" not in exported
