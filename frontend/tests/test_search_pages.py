from types import SimpleNamespace

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from frontend.clients import backend_client as client
from frontend.components.top_navigation import FEATURES
from frontend.core import session


def payload(kind="consultation"):
    return {
        "request_id": "search-test", "query": "test", "category": "consumer",
        "total": 1, "is_mock": False,
        "items": [{
            "evidence_id": "e-1", "document_id": "1", "title": "Search title",
            "content": "Search content", "source": {
                "source_id": "1", "title": "Source", "source_type": kind,
                "url": "https://example.test/document",
            },
        }],
    }


@pytest.mark.parametrize("kind,source", [("laws", "law"), ("consultations", "consultation"), ("cases", "case")])
def test_search_endpoint_contract(monkeypatch, kind, source):
    calls = []
    def request(method, path, **kwargs):
        calls.append((method, path, kwargs))
        return payload(source)
    monkeypatch.setattr(client, "_request", request)
    result = getattr(client, "search_" + kind)("consumer", " test ")
    assert result["items"][0]["source"]["source_type"] == source
    assert calls == [("GET", "/api/legal/" + kind, {"params": {"category": "consumer", "query": "test", "top_k": 3}})]


@pytest.mark.parametrize("change", [
    {"total": 2}, {"is_mock": True}, {"category": "labor"}, {"query": "wrong"},
    {"request_id": ""}, {"items": None},
])
def test_invalid_response_is_not_an_empty_result(monkeypatch, change):
    data = payload()
    data.update(change)
    monkeypatch.setattr(client, "_request", lambda *a, **kw: data)
    with pytest.raises(client.BackendClientError, match="계약"):
        client.search_consultations("consumer", "test")


def test_wrong_type_and_legacy_stub_rejected(monkeypatch):
    for data in [payload("case"), {"items": [], "total": 0, "category": "consumer", "query": "test"}]:
        monkeypatch.setattr(client, "_request", lambda *a, data=data, **kw: data)
        with pytest.raises(client.BackendClientError):
            client.search_consultations("consumer", "test")


def test_empty_and_error_are_distinct(monkeypatch):
    data = payload()
    data.update(items=[], total=0)
    monkeypatch.setattr(client, "_request", lambda *a, **kw: data)
    assert client.search_consultations("consumer", "test")["items"] == []
    def fail(*a, **kw):
        raise client.BackendClientError("MCP error")
    monkeypatch.setattr(client, "_request", fail)
    with pytest.raises(client.BackendClientError):
        client.search_consultations("consumer", "test")


def test_validation_before_network(monkeypatch):
    def forbidden(*a, **kw):
        pytest.fail("Invalid input must not call network")
    monkeypatch.setattr(client, "_request", forbidden)
    for query in [" ", "x", "x" * 201]:
        with pytest.raises(client.BackendClientError):
            client.search_laws("consumer", query)
    response = httpx.Response(422, json={"detail": [{"msg": "raw internal validation"}]})
    assert client._extract_api_error(response)[0] == "VALIDATION_ERROR"


def test_six_navigation_items():
    assert [x[0] for x in FEATURES] == ["analysis", "faq", "history"]


def test_category_change_and_legacy_navigation(monkeypatch):
    class State(dict):
        __getattr__ = dict.__getitem__
        __setattr__ = dict.__setitem__
    state = State()
    monkeypatch.setattr(session, "st", SimpleNamespace(session_state=state))
    session.initialize_session()
    state.selected_category = "consumer"
    state.selected_feature = "documents"
    state.consultation_results = [payload()]
    state.consultation_query = "old"
    state.search_errors = {"cases": "old"}
    session.initialize_session()
    assert state.selected_feature == "analysis"
    session.select_category("housing")
    assert state.consultation_results is None
    assert state.consultation_query == state.law_query == state.case_query == ""
    assert state.search_errors == {}


def test_search_page_clears_stale_results_and_displays_source():
    data = payload()["items"]
    app = AppTest.from_string(
        "import streamlit as st\n"
        "from frontend.core.session import initialize_session\n"
        "from frontend.components.search_page import render_search_page\n"
        "initialize_session()\n"
        "class Service:\n"
        "    def search_consultations(self, category, query):\n"
        "        if query == 'fail': raise ValueError('search failed')\n"
        "        if query == 'empty': return []\n"
        f"        return {ascii(data)}\n"
        "    search_laws = search_cases = search_consultations\n"
        "render_search_page('consumer', 'consultations', Service())\n"
    ).run()
    assert not app.exception
    app.text_input(key="consultation_query").set_value("test")
    app.button[0].click().run()
    assert app.session_state["consultation_results"]
    assert any("Search content" in x.value for x in app.markdown)
    assert len(app.get("link_button")) == 0
    app.text_input(key="consultation_query").set_value("fail")
    app.button[0].click().run()
    assert app.session_state["consultation_results"] is None
    assert any("search failed" in x.value for x in app.error)
    assert not any("Search content" in x.value for x in app.markdown)
    app.text_input(key="consultation_query").set_value("empty")
    app.button[0].click().run()
    assert not app.error
    assert app.session_state["consultation_results"] == []
    assert not app.exception
