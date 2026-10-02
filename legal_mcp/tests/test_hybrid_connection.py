from contextlib import contextmanager

import pytest

from legal_mcp.repositories import legal_repository as module


@pytest.mark.parametrize("types,method", [(["LAW"], "_search_laws"),
                                        (["CASE"], "_search_cases"),
                                        (["CONSULTATION"], "_search_legal_documents"),
                                        (["LAW", "CASE"], "_search_legal_documents")])
@pytest.mark.parametrize("failure", [None, "vector", "keyword"])
def test_hybrid_connection_dispatch_order_and_failure_cleanup(monkeypatch, types, method, failure):
    events = []
    cursor = object()

    class Connection:
        @contextmanager
        def cursor(self):
            events.append("cursor open")
            try:
                yield cursor
            finally:
                events.append("cursor close")

    @contextmanager
    def connection():
        events.append("connection open")
        try:
            yield Connection()
        finally:
            events.append("connection close")

    repo = module.LegalRepository()

    def vector(cur, *args):
        assert cur is cursor
        assert args == (([0.1], "labor", 9) if len(types) == 1 and types[0] in {"LAW", "CASE"}
                        else ([0.1], "labor", types, 9))
        events.append("vector")
        if failure == "vector":
            raise ValueError("vector failed")
        return [{"document_id": 1}]

    def keyword(cur, query, category, document_types, limit):
        assert cur is cursor and (category, document_types, limit) == ("labor", types, 9)
        events.append(query)
        if failure == "keyword" and query == "second":
            raise ValueError("keyword failed")
        return [{"term": query}]

    monkeypatch.setattr(module, "get_connection", connection)
    monkeypatch.setattr(repo, method, vector)
    monkeypatch.setattr(repo, "_search_documents_by_keyword", keyword)
    if failure:
        with pytest.raises(ValueError):
            repo.search_hybrid_candidates([0.1], ["first", "second"], "labor", types, 9)
    else:
        assert repo.search_hybrid_candidates([0.1], ["first", "second"], "labor", types, 9) == (
            [{"document_id": 1}], [{"term": "first"}, {"term": "second"}])
    assert events.count("connection open") == 1
    assert events[-2:] == ["cursor close", "connection close"]
    assert events[2] == "vector"
    if failure != "vector":
        assert events[3:5] == ["first", "second"]
