"""Process-owned connection pool; identity and timeout belong to each request."""
import atexit
from http.cookiejar import CookieJar, DefaultCookiePolicy
from threading import Lock

import httpx


class _RejectCookies(DefaultCookiePolicy):
    def set_ok(self, cookie, request):
        return False


_lock = Lock()
_client: httpx.Client | None = None


def get_client() -> httpx.Client:
    global _client
    with _lock:
        if _client is None:
            _client = httpx.Client(cookies=CookieJar(policy=_RejectCookies()))
        return _client


def request(method: str, url: str, **kwargs) -> httpx.Response:
    return get_client().request(method, url, **kwargs)


def close_client() -> None:
    """Process shutdown cleanup; not called during normal UI requests."""
    global _client
    with _lock:
        client, _client = _client, None
    if client is not None:
        client.close()


atexit.register(close_client)
