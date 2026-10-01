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
