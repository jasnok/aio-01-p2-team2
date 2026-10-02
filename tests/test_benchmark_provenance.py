import json

import pytest
from pydantic import ValidationError

from scripts.benchmark_provenance import capture, finish
from frontend.core.portfolio_evidence import MeasurementProvenance


def test_capture_excludes_secrets_and_detects_code_changes(tmp_path, monkeypatch):
    marker = "SECRET-MUST-NOT-BE-RECORDED"
    monkeypatch.setenv("OPENAI_API_KEY", marker)
    monkeypatch.setenv("DATABASE_URL", marker)
    (tmp_path / "requirements-constraints.txt").write_text("openai==2.54.0\n")
    source = tmp_path / "code.py"
    source.write_bytes(b"print(1)\r\n")
    report = capture(["code.py"], ["openai"], tmp_path)
    assert marker not in json.dumps(report)
    assert report["git_head"] is None
    source.write_bytes(b"print(1)\n")
    report = finish(report, ["code.py"], ["openai"], tmp_path)
    assert report["code_unchanged_during_measurement"]
    MeasurementProvenance.model_validate(report)
    source.write_text("print(2)\n")
    changed = finish(report, ["code.py"], ["openai"], tmp_path)
    assert not changed["code_unchanged_during_measurement"]
    with pytest.raises(ValidationError):
        MeasurementProvenance.model_validate(changed)


def test_metadata_contract_rejects_unknown_fields_and_partial_database():
    from frontend.core.portfolio_evidence import load_evidence
    report = load_evidence().provenance["keyword"].model_dump(mode="json")
    report["api_key"] = "never-export-this"
    with pytest.raises(ValidationError):
        MeasurementProvenance.model_validate(report)
    report.pop("api_key")
    report["database_after"] = None
    with pytest.raises(ValidationError):
        MeasurementProvenance.model_validate(report)
