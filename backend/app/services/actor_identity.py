"""Separate guest identifiers from authenticated account identifiers."""


def actor_key(actor: dict) -> tuple[str, str]:
    role = actor.get("role")
    if role not in {"GUEST", "USER", "ADMIN"} or actor.get("id") is None:
        raise ValueError("Invalid actor identity")
    return ("guest" if role == "GUEST" else "member", str(actor["id"]))


def owns_run(actor: dict, run: dict) -> bool:
    stored = run.get("actor")
    if not isinstance(stored, dict):
        return False
    try:
        return str(run.get("owner_id")) == str(stored.get("id")) and actor_key(actor) == actor_key(stored)
    except ValueError:
        return False


def record_owner(record: dict) -> dict:
    return {"id": record.get("owner_id"), "role": record.get("owner_role")}


def owns_record(actor: dict, record: dict) -> bool:
    try:
        return actor_key(actor) == actor_key(record_owner(record))
    except ValueError:
        return False
