from pathlib import Path

from streamlit.testing.v1 import AppTest


APP = Path(__file__).parents[1] / "app.py"


def test_all_local_frontend_features_render() -> None:
    app = AppTest.from_file(str(APP)).run(timeout=20)
    assert not app.exception

    app.button(key="category-housing").click().run(timeout=20)
    app.text_area(key="question_message").set_value("계약이 끝났는데 보증금을 받지 못했습니다.")
    next(button for button in app.button if button.label == "✦ 사례 분석하기").click().run(timeout=20)
    assert not app.exception
    assert app.session_state["last_result"]["agent_id"] == "housing"
    assert sum(expander.label == "상세보기" for expander in app.expander) >= 2
    assert not any("QA 빠른 테스트" in expander.label for expander in app.expander)
    assert not app.get("link_button")
    expected_widgets = {"nav-faq": ("expander", 2)}
    for key, (widget, minimum) in expected_widgets.items():
        app.button(key=key).click().run(timeout=20)
        assert not app.exception
        assert len(getattr(app, widget)) >= minimum

    app.button(key="nav-history").click().run(timeout=20)
    assert not app.exception
    assert app.session_state["session_history"]
