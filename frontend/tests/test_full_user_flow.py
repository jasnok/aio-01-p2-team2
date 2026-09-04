from pathlib import Path

from streamlit.testing.v1 import AppTest


APP = Path(__file__).parents[1] / "app.py"


def test_all_local_frontend_features_render() -> None:
    app = AppTest.from_file(str(APP)).run(timeout=20)
    assert not app.exception

    app.button(key="category-housing").click().run(timeout=20)
    app.text_area[0].set_value("계약이 끝났는데 보증금을 받지 못했습니다.")
    next(button for button in app.button if button.label == "✦ 사례 분석하기").click().run(timeout=20)
    assert not app.exception
    assert app.session_state["last_result"]["agent_id"] == "housing"
    assert any(expander.label == "법령 상세 보기" for expander in app.expander)
    assert any(expander.label == "판례 상세 보기" for expander in app.expander)

    app.sidebar.button(key="nav-laws").click().run(timeout=20)
    app.text_input[0].set_value("보증금")
    next(button for button in app.button if button.label == "검색하기").click().run(timeout=20)
    assert app.session_state["law_results"]

    app.sidebar.button(key="nav-cases").click().run(timeout=20)
    app.text_input[0].set_value("보증금")
    next(button for button in app.button if button.label == "검색하기").click().run(timeout=20)
    assert app.session_state["case_results"]

    expected_widgets = {
        "nav-terms": ("text_input", 1),
        "nav-documents": ("checkbox", 4),
        "nav-actions": ("checkbox", 5),
        "nav-faq": ("expander", 2),
    }
    for key, (widget, minimum) in expected_widgets.items():
        app.sidebar.button(key=key).click().run(timeout=20)
        assert not app.exception
        assert len(getattr(app, widget)) >= minimum

    app.sidebar.button(key="nav-history").click().run(timeout=20)
    assert not app.exception
    assert app.session_state["session_history"]
