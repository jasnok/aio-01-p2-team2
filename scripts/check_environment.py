"""Verify installed distributions against repository constraints; print no secrets."""
import argparse
import hashlib
import json
import platform
import sys
from importlib.metadata import distributions
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--constraints", type=Path,
                        default=Path(__file__).resolve().parents[1] / "requirements-constraints.txt")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    raw = args.constraints.read_bytes()
    pins = {}
    errors = []
    for line in raw.decode("utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        requirement = Requirement(line)
        if requirement.marker is None or requirement.marker.evaluate():
            specifiers = list(requirement.specifier)
            if len(specifiers) != 1 or specifiers[0].operator != "==" or "*" in specifiers[0].version:
                errors.append(f"constraint must select an exact version: {requirement.name}")
            pins[canonicalize_name(requirement.name)] = requirement.specifier
    packages = {canonicalize_name(d.metadata["Name"]): d.version for d in distributions()
                if canonicalize_name(d.metadata["Name"]) not in {"pip", "setuptools", "wheel"}}
    if sys.version_info[:2] != (3, 12):
        errors.append("Python 3.12 is required")
    for name, version in sorted(packages.items()):
        if name not in pins:
            errors.append(f"unconstrained distribution: {name}=={version}")
        elif version not in pins[name]:
            errors.append(f"version mismatch: {name}=={version}; expected {pins[name]}")
    result = {"python": platform.python_version(), "platform": platform.system(),
              "constraints_sha256": hashlib.sha256(raw).hexdigest(),
              "packages": dict(sorted(packages.items())), "errors": errors}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"python": result["python"], "platform": result["platform"],
                      "packages": len(packages), "errors": errors}))
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
