from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from legal_mcp.providers import embedding_provider as module


@pytest.fixture
def server_app(monkeypatch):
    from mcp.server.fastmcp import FastMCP
    from legal_mcp import server

    # MCP session managers are deliberately single-use per server instance.
    monkeypatch.setattr(server, "mcp", FastMCP("lifecycle-test", stateless_http=True))
    return server.create_app()


@pytest.fixture
def clients(monkeypatch):
    instances = []

    class Provider:
        def __init__(self, model, dimension, api_key):
            self.settings = model, dimension, api_key
            self.closed = 0
            instances.append(self)

        def embed(self, texts):
            return [[float(len(text))] for text in texts]

        def close(self):
            self.closed += 1

    pool = module.EmbeddingClients()
    monkeypatch.setattr(module, "OpenAIEmbeddingProvider", Provider)
    monkeypatch.setattr(module, "_clients", pool)
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key")
    module._query_cache.clear()
    yield pool, instances
    pool.close()
    module._query_cache.clear()


def test_distinct_queries_share_client_and_configuration_changes_retire_it(clients, monkeypatch):
    pool, instances = clients
    module.create_embedding("one")
    module.create_embedding("another")
    assert len(instances) == 1
    for name, value in [("EMBEDDING_MODEL", "other"), ("EMBEDDING_DIMENSION", "1"),
                        ("OPENAI_API_KEY", "other-key")]:
        monkeypatch.setenv(name, value)
        module.create_embedding("new")
    assert len(instances) == 4
    assert [p.closed for p in instances] == [1, 1, 1, 0]
    pool.close()
    pool.close()
    assert all(p.closed == 1 for p in instances)
    module.create_embedding("after-restart")
    assert len(instances) == 5


def test_concurrent_creation_is_single_and_embedding_is_not_serialized(clients):
    pool, instances = clients
    entered, release = Event(), Event()

    def first():
        with pool.acquire(("same",), "model", 1, "key"):
            entered.set()
            assert release.wait(3)

    with ThreadPoolExecutor(2) as executor:
        pending = executor.submit(first)
        assert entered.wait(3)
        with pool.acquire(("same",), "model", 1, "key") as provider:
            assert provider is instances[0]
        release.set()
        pending.result(timeout=3)
    assert len(instances) == 1


def test_rotation_and_shutdown_wait_for_old_inflight_client(clients):
    pool, instances = clients
    entered, release = Event(), Event()

    def first():
        with pool.acquire(("old",), "model", 1, "key"):
            entered.set()
            assert release.wait(3)

    with ThreadPoolExecutor(2) as executor:
        worker = executor.submit(first)
        assert entered.wait(3)
        with pool.acquire(("new",), "model", 1, "new-key"):
            pass
        assert instances[0].closed == 0
        closing = executor.submit(pool.close)
        # Observe the actual state transition, without a timing-based sleep.
        with pool.condition:
            assert pool.condition.wait_for(lambda: pool.closing, timeout=3)
        assert not closing.done()
        release.set()
        worker.result(timeout=3)
        closing.result(timeout=3)
    assert [p.closed for p in instances] == [1, 1]


def test_failed_initialization_and_embedding_can_retry(clients, monkeypatch):
    pool, instances = clients
    original = module.OpenAIEmbeddingProvider
    monkeypatch.setattr(module, "OpenAIEmbeddingProvider", lambda *args: (_ for _ in ()).throw(ValueError("failed")))
    with pytest.raises(ValueError):
        module.create_embedding("retry")
    monkeypatch.setattr(module, "OpenAIEmbeddingProvider", original)
    assert module.create_embedding("retry") == [5.0]
    assert len(instances) == 1
    assert pool.current.users == 0


def test_server_lifespan_closes_clients_even_on_failure(clients, server_app):
    import asyncio

    pool, instances = clients
    module.create_embedding("server")

    async def run():
        app = server_app
        with pytest.raises(ExceptionGroup) as caught:
            async with app.router.lifespan_context(app):
                raise ValueError("server failure")
        assert isinstance(caught.value.exceptions[0], ValueError)

    asyncio.run(run())
    assert instances[0].closed == 1


def test_embedding_failure_releases_lease_and_does_not_cache_error(clients, monkeypatch):
    pool, instances = clients
    original = module.OpenAIEmbeddingProvider.embed
    monkeypatch.setattr(module.OpenAIEmbeddingProvider, "embed", lambda *args: (_ for _ in ()).throw(ValueError("API failure")))
    with pytest.raises(ValueError):
        module.create_embedding("retry")
    assert pool.current.users == 0
    monkeypatch.setattr(module.OpenAIEmbeddingProvider, "embed", original)
    assert module.create_embedding("retry") == [5.0]
    assert len(instances) == 1


def test_shutdown_remains_reusable_after_close_error(clients, monkeypatch):
    pool, instances = clients
    module.create_embedding("first")
    original = instances[0].close

    def fail():
        original()
        raise ValueError("close failure")

    monkeypatch.setattr(instances[0], "close", fail)
    with pytest.raises(ValueError):
        pool.close()
    assert not pool.closing
    assert pool.entries == []
    module.create_embedding("second")
    assert len(instances) == 2


def test_server_normal_shutdown(clients, server_app):
    import asyncio

    async def run():
        app = server_app
        async with app.router.lifespan_context(app):
            module.create_embedding("normal")

    asyncio.run(run())
    assert clients[1][0].closed == 1


def test_server_cancellation_still_closes_client(clients, server_app):
    import anyio

    async def run():
        app = server_app
        with anyio.CancelScope() as scope:
            async with app.router.lifespan_context(app):
                module.create_embedding("cancel")
                scope.cancel()
                await anyio.sleep(0)

    anyio.run(run)
    assert clients[1][0].closed == 1
