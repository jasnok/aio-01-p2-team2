"""Allowlisted measurement provenance; never serialize configuration or URLs."""
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
from pathlib import Path
import platform
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def capture(code_paths, packages, root=ROOT):
    def git(*args):
        result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
        return result.stdout.strip() if result.returncode == 0 else None

    head = git("rev-parse", "HEAD")
    dirty = git("status", "--porcelain")
    return {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "git_head": head,
        "working_tree_dirty": bool(dirty) if dirty is not None else None,
        "python": platform.python_version(), "platform": platform.system(),
        "packages": {name: version(name) for name in packages},
        "constraints_sha256": hashlib.sha256((root / "requirements-constraints.txt").read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
        "code_sha256": {name: hashlib.sha256((root / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest() for name in code_paths},
    }


def finish(provenance, code_paths, packages, root=ROOT):
    current = capture(code_paths, packages, root)
    provenance["finished_at"] = datetime.now(timezone.utc).isoformat()
    provenance["code_unchanged_during_measurement"] = current["code_sha256"] == provenance["code_sha256"]
    return provenance


def database_profile():
    from legal_mcp.infrastructure.database import get_connection
    from legal_mcp.core.config import get_settings
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT (SELECT count(*) FROM legal_documents) AS documents, (SELECT count(*) FROM legal_chunks) AS chunks")
            counts = cursor.fetchone()
        return {"documents": counts["documents"], "chunks": counts["chunks"],
                "postgres_version_num": connection.info.server_version,
                "revision_declared": get_settings().retrieval_dataset_revision,
                "immutable_snapshot": False}
