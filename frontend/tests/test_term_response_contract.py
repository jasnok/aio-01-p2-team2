from copy import deepcopy

import pytest
from streamlit.testing.v1 import AppTest

from frontend.clients import backend_client as api
from frontend.services.api_legal_service import ApiLegalService


@pytest.mark.parametrize('payload', [
    {}, {'items': None}, {'items': {}}, {'items': [{}]},
    {'items': [{'term': '용어'}]},
    {'items': [{'term': 7, 'description': '설명'}]},
    {'items': [{'term': '', 'description': '설명'}]},
    {'items': [{'term': '용어', 'description': None}]},
    {'items': [{'term': '용어', 'description': ''}]},
])
def test_invalid_search_response_is_a_contract_error(payload, monkeypatch):
    monkeypatch.setattr(api, '_request', lambda *a, **kw: deepcopy(payload))
    with pytest.raises(api.BackendClientError) as error:
        api.search_terms('housing', '용어')
    assert error.value.code == 'CONTRACT_MISMATCH'


@pytest.mark.parametrize('patch', [
    {'terms': None}, {'terms': {}}, {'terms': ['invalid']}, {'terms': [[]]},
    {'terms': [['용어']]}, {'terms': [['용어', '설명', 'extra']]},
    {'terms': [[False, '설명']]}, {'terms': [['용어', None]]},
    {'terms': [['', '설명']]}, {'terms': [['용어', '']]},
    {'category': 'labor'}, {'category': None},
])
def test_invalid_catalog_response_is_a_contract_error(patch, monkeypatch):
    payload = {'category': 'housing', 'terms': [['용어', '설명']], **patch}
    monkeypatch.setattr(api, '_request', lambda *a, **kw: payload)
    with pytest.raises(api.BackendClientError) as error:
        api.get_category_catalog('housing')
    assert error.value.code == 'CONTRACT_MISMATCH'


@pytest.mark.parametrize('catalog', [{}, {'terms': []}])
def test_missing_required_catalog_fields_are_rejected(catalog, monkeypatch):
    monkeypatch.setattr(api, '_request', lambda *a, **kw: catalog)
    with pytest.raises(api.BackendClientError) as error:
        api.get_category_catalog('housing')
    assert error.value.code == 'CONTRACT_MISMATCH'


@pytest.mark.parametrize('query', ['', '용어'])
def test_terms_screen_shows_controlled_error_for_bad_response(query, monkeypatch):
    monkeypatch.setattr(api, '_request', lambda *a, **kw: {'category': 'housing', 'terms': [['용어']], 'items': [{}]})
    app = AppTest.from_string(f'''
import streamlit as st
from frontend.services.api_legal_service import ApiLegalService
from frontend.components.helper_sections import render_helper_feature
st.session_state['term-query-housing'] = {query!r}
render_helper_feature('housing', 'terms', ApiLegalService('session'))
''').run()
    assert not app.exception
    assert app.error


@pytest.mark.parametrize('empty', [False, True])
def test_valid_catalog_and_search_keep_existing_fields_and_view_shape(empty, monkeypatch):
    terms = [] if empty else [['용어', '설명']]
    items = [] if empty else [{'term': '용어', 'description': '설명'}]
    catalog = {'category': 'housing', 'terms': terms, 'documents': ['기존 서류'], 'name': '주거'}
    search = {'items': items}
    original = deepcopy(catalog)
    monkeypatch.setattr(api, '_request', lambda method, path, **kw: catalog if '/catalog/' in path else search)
    assert api.get_category_catalog('housing') == catalog
    assert api.search_terms('housing', '용어') == search
    service = ApiLegalService('session')
    expected = [] if empty else [('용어', '설명')]
    assert service.search_terms('housing', '') == expected
    assert service.search_terms('housing', '용어') == expected
    assert catalog == original
