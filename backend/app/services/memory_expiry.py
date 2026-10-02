"""Expired-entry cleanup for process-local development stores."""


def remove_expired_entries(entries: dict, now: float) -> None:
    """Caller holds the store lock; never evict an unexpired entry."""
    expired = [key for key, (_, expires_at) in entries.items() if expires_at <= now]
    for key in expired:
        del entries[key]
