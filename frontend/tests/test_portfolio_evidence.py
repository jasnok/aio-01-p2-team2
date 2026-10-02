import json

import pytest
from streamlit.testing.v1 import AppTest

from frontend.core.portfolio_evidence import load_evidence
from scripts.build_portfolio_evidence import ROOT, build


def test_generated_evidence_matches_sources_without_questions_or_credentials():
    report = build(ROOT / "output" / "portfolio")
    assert report == load_evidence()
    assert len(report.rows) == 4
    text = report.model_dump_json()
    assert '"query"' not in text
    assert '"terms"' not in text
    assert '"api_key"' not in text
    assert '"content"' not in text


def test_line_endings_do_not_change_source_fingerprints(tmp_path):
    directory = ROOT / "output" / "portfolio"
    for name in [source.file for source in build(directory).sources]:
        text = (directory / name).read_text(encoding="utf-8")
        (tmp_path / name).write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
    assert build(directory) == build(tmp_path)


def test_corrupted_measurements_are_rejected(tmp_path):
    directory = ROOT / "output" / "portfolio"
    for source in build(directory).sources:
        (tmp_path / source.file).write_bytes((directory / source.file).read_bytes())
    path = tmp_path / next(source.file for source in build(directory).sources if source.file.startswith("embedding-client"))
    data = json.loads(path.read_text(encoding="utf-8"))
    data["results"]["new_client"]["median_ms"] = 0
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="median"):
        build(tmp_path)


def test_panel_renders_scopes_chart_limits_and_download():
    app = AppTest.from_string(
        "from frontend.components.portfolio_evidence import render_portfolio_evidence\n"
        "render_portfolio_evidence()"
    ).run(timeout=20)
    assert not app.exception
    assert app.warning
    assert app.get("download_button")
    assert len(app.dataframe[0].value) == 3
    app.selectbox[0].select("SDK 클라이언트 획득").run(timeout=20)
    assert not app.exception
    assert len(app.dataframe[0].value) == 1


def test_missing_artifact_is_visible_warning(monkeypatch):
    from frontend.components import portfolio_evidence as panel
    monkeypatch.setattr(panel, "load_evidence", lambda: (_ for _ in ()).throw(FileNotFoundError()))
    app = AppTest.from_string(
        "from frontend.components.portfolio_evidence import render_portfolio_evidence\n"
        "render_portfolio_evidence()"
    ).run(timeout=20)
    assert not app.exception
    assert len(app.warning) == 1
    assert not app.get("download_button")
