from concurrent.futures import ThreadPoolExecutor
from threading import Event
import pytest
from legal_mcp.core.cache import QueryCache


def test_concurrent_cold_queries_share_one_loader_and_return_defensive_copies():
    cache = QueryCache()
    started, release = Event(), Event()
    calls = []
    def load():
        calls.append(1)
        started.set()
        assert release.wait(2)
        return {"items": [1]}
    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(cache.get_or_load, "query", load, 30)
        assert started.wait(2)
        second = pool.submit(cache.get_or_load, "query", load, 30)
        release.set()
        left, right = first.result(), second.result()
    left["items"].append(2)
    assert right == {"items": [1]}
    assert len(calls) == 1


def test_expiration_capacity_and_disabled_cache():
    now = [0]
    cache = QueryCache(max_entries=1, clock=lambda: now[0])
    calls = []
    def load():
        calls.append(1)
        return len(calls)
    assert cache.get_or_load("a", load, 10) == 1
    assert cache.get_or_load("a", load, 10) == 1
    now[0] = 11
    assert cache.get_or_load("a", load, 10) == 2
    cache.get_or_load("b", load, 10)
    assert list(cache.values) == ["b"]
    assert cache.get_or_load("b", load, 0) == 4


def test_errors_are_not_cached_and_pending_request_is_released():
    cache = QueryCache()
    def fail():
        raise ValueError("failed")
    with pytest.raises(ValueError):
        cache.get_or_load("a", fail, 30)
    assert not cache.pending
    assert cache.get_or_load("a", lambda: "recovered", 30) == "recovered"
