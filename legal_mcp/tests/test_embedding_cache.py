from legal_mcp.providers import embedding_provider as module


def test_reuses_identical_query_but_isolates_models_and_defends_mutation(monkeypatch):
    calls = []
    class Provider:
        def embed(self, texts):
            calls.append(texts)
            return [[0.1, 0.2]]
    module._query_cache.clear()
    monkeypatch.setattr(module, "OpenAIEmbeddingProvider", Provider)
    first = module.create_embedding("퇴직금")
    first[0] = 9
    assert module.create_embedding("퇴직금") == [0.1, 0.2]
    assert len(calls) == 1
    monkeypatch.setenv("EMBEDDING_MODEL", "other-model")
    module.create_embedding("퇴직금")
    assert len(calls) == 2
    module._query_cache.clear()
