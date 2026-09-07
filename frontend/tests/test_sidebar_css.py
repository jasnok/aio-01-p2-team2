from pathlib import Path


THEME = Path(__file__).parents[1] / "styles" / "theme.css"


def test_sidebar_width_is_only_for_expanded_state() -> None:
    css = THEME.read_text(encoding="utf-8")

    assert 'section[data-testid="stSidebar"][aria-expanded="true"]' in css
    assert 'section[data-testid="stSidebar"][aria-expanded="false"]' in css
    assert 'section[data-testid="stSidebar"] > div { width: 270px !important; }' not in css
    assert "visibility: hidden" in css


def test_small_screen_layout_has_wrapping_rules() -> None:
    css = THEME.read_text(encoding="utf-8")

    assert "@media (max-width: 640px)" in css
    assert "flex-wrap: wrap" in css
    assert "flex: 1 1 100%" in css
