import pytest
from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


@pytest.mark.parametrize('category', ['housing', 'labor', 'consumer'])
def test_every_catalog_term_is_searchable_with_the_same_description(category):
    catalog = client.get(f'/api/catalog/{category}')
    assert catalog.status_code == 200
    terms = catalog.json()['terms']
    assert terms
    for term, description in terms:
        response = client.get('/api/legal/terms', params={'category': category, 'query': term})
        assert response.status_code == 200
        assert {'term': term, 'description': description} in response.json()['items']
        described = client.get('/api/legal/terms', params={'category': category, 'query': description})
        assert {'term': term, 'description': description} in described.json()['items']


@pytest.mark.parametrize('category,query', [('housing', '보증금'), ('labor', '임금체불'), ('consumer', '청약철회')])
def test_existing_searches_still_work_and_surrounding_whitespace_is_trimmed(category, query):
    plain = client.get('/api/legal/terms', params={'category': category, 'query': query}).json()
    spaced = client.get('/api/legal/terms', params={'category': category, 'query': f'  {query}  '}).json()
    assert plain['items']
    assert spaced == plain


def test_search_stays_in_selected_category_and_unknown_term_is_empty():
    for query in ['내용증명', '없는용어']:
        result = client.get('/api/legal/terms', params={'category': 'consumer', 'query': query})
        assert result.status_code == 200
        assert result.json()['items'] == []


@pytest.mark.parametrize('category,query', [('invalid', '보증금'), ('housing', ' '),
                                           ('housing', '  '), ('housing', ' a '),
                                           ('housing', '가' * 201)])
def test_invalid_search_inputs_are_rejected(category, query):
    response = client.get('/api/legal/terms', params={'category': category, 'query': query})
    assert response.status_code == 422
