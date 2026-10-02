import os
from contextlib import contextmanager

import pytest

from legal_mcp.repositories import legal_repository as module


def test_empty_batch_does_not_open_connection(monkeypatch):
    monkeypatch.setattr(module, "get_connection", lambda: pytest.fail("unneeded connection"))
    assert module.LegalRepository().search_documents_by_keywords([], "labor", ["LAW"]) == []


def test_batch_shares_connection_and_closes_it_on_query_failure(monkeypatch):
    events = []

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            events.append("cursor closed")

        def execute(self, sql, parameters):
            events.append(parameters[0])
            if parameters[0] == "failure":
                raise ValueError("query failed")

        def fetchall(self):
            return [{"document_id": 1}]

    class Connection:
        def cursor(self):
            return Cursor()

    @contextmanager
    def connection():
        events.append("opened")
        try:
            yield Connection()
        finally:
            events.append("closed")

    monkeypatch.setattr(module, "get_connection", connection)
    repo = module.LegalRepository()
    assert repo.search_documents_by_keywords(["first", "second"], "labor", ["LAW"]) == [
        {"document_id": 1}, {"document_id": 1}]
    assert events == ["opened", "first", "second", "cursor closed", "closed"]
    events.clear()
    with pytest.raises(ValueError):
        repo.search_documents_by_keywords(["first", "failure", "third"], "labor", ["LAW"])
    assert events == ["opened", "first", "failure", "cursor closed", "closed"]


@pytest.mark.skipif(not os.getenv("RUN_POSTGRES_INTEGRATION"), reason="explicit PostgreSQL test URL required")
def test_real_postgres_batch_preserves_per_term_limits_scores_and_chunk_ties(monkeypatch):
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(os.environ["RUN_POSTGRES_INTEGRATION"], row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("""CREATE TEMP TABLE legal_documents (
                id integer, document_type text, category text, law_name text,
                article_number text, title text, case_number text, case_name text,
                court text, decided_at text, judgment_result text, summary text,
                effective_date text, source_name text, source_url text, content text)""")
            cur.execute("""CREATE TEMP TABLE legal_chunks (
                document_id integer, chunk_index integer, content text)""")
            cur.execute("""INSERT INTO legal_documents (id,document_type,category,law_name,content)
                VALUES (1,'LAW','labor','임금','임금 퇴직금'),
                       (2,'LAW','labor','임금','임금'),
                       (3,'LAW','labor','퇴직금','퇴직금'),
                       (4,'LAW','housing','임금','임금'),
                       (5,'CASE','labor','임금','임금'),
                       (6,'LAW','labor','O''Brien','O''Brien')""")
            cur.execute("""INSERT INTO legal_chunks VALUES
                (1,1,'임금 second'), (1,0,'임금 first'), (3,0,'퇴직금')""")

        calls = []

        @contextmanager
        def connection():
            calls.append(1)
            yield conn

        monkeypatch.setattr(module, "get_connection", connection)
        repo = module.LegalRepository()
        terms = [" 임금 ", "퇴직금", "O'Brien", "missing"]
        baseline = [row for term in terms for row in
                    repo.search_documents_by_keyword(term, "labor", ["LAW"], 2)]
        assert len(calls) == 4
        calls.clear()
        batch = repo.search_documents_by_keywords(terms, "labor", ["LAW"], 2)
        assert len(calls) == 1
        assert batch == baseline
        assert [row["document_id"] for row in batch] == [1, 2, 3, 1, 6]
        assert [float(row["keyword_score"]) for row in batch] == [1, 1, 1, 0.5, 1]
        assert batch[0]["chunk_content"] == "임금 first"
        assert batch[1]["chunk_content"] == "임금"


def test_service_batches_extracted_terms_without_changing_fusion(monkeypatch):
    from legal_mcp.services import legal_search_service as service_module
    from legal_mcp.core.config import Settings

    calls = []

    class Repository:
        def search_hybrid_candidates(self, **kwargs):
            calls.append(kwargs)
            return ([{"document_id": 1, "similarity": 0.9}],
                    [{"document_id": 2, "keyword_score": 1.0}])

    monkeypatch.setattr(service_module, "create_embedding", lambda query: [0.1])
    service = service_module.LegalSearchService.__new__(service_module.LegalSearchService)
    service.settings = Settings(database_url="postgresql://test", openai_api_key="fake", _env_file=None)
    service.repository = Repository()
    service._hybrid_search_uncached("임금과 퇴직금", "labor", ["LAW"], 3)
    assert len(calls) == 1
    assert calls[0]["queries"] == ["임금과 퇴직금", "퇴직금", "임금"]
    assert calls[0]["limit"] == max(9, service.settings.retrieval_top_k)
