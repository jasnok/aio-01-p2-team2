"""Exercise the CI environment gate without installing or calling external APIs."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("replacement, expected", [("openai==0.0.0", "version mismatch: openai"),
                                                   ("# missing openai pin", "unconstrained distribution: openai"),
                                                   ("openai>=1", "constraint must select an exact version: openai")])
def test_environment_gate_rejects_changed_or_missing_sdk_pin(tmp_path, replacement, expected):
    source = (ROOT / "requirements-constraints.txt").read_text(encoding="utf-8")
    lines = [replacement if line.startswith("openai==") else line for line in source.splitlines()]
    constraints = tmp_path / "constraints.txt"
    constraints.write_text("\n".join(lines), encoding="utf-8")
    completed = subprocess.run([sys.executable, str(ROOT / "scripts/check_environment.py"),
        "--constraints", str(constraints)], capture_output=True, text=True, check=False)
    assert completed.returncode == 1
    result = json.loads(completed.stdout)
    assert any(expected in error for error in result["errors"])
