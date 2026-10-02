from copy import deepcopy

import pytest

from frontend.clients import backend_client as api
from frontend.clients.agent_stream import final_result
from frontend.services.history_service import parse_page


RAW = dict(request_id='req', agent_id='consumer', status='completed',
           termination_reason='model_finished', question_summary='요약',
           answer='자료를 확인하세요.', is_mock=False)
CLAIMS = [{'text': '확인할 주장', 'citations': [{'evidence_id': 'law-1', 'quote': '원문 인용'}]}]


def read_result(boundary, payload, monkeypatch):
    if boundary == 'http':
        monkeypatch.setattr(api, '_request', lambda *args, **kwargs: payload)
        return api.ask_legal_question('consumer', '질문입니다.', 'session')
    if boundary == 'sse':
        return final_result(dict(run_id='run', status='completed', result=payload), 'run')
    page = parse_page({'items': [{'id': 1, 'type': 'analysis', 'result': payload}]})
    return page['items'][0]['result']


@pytest.mark.parametrize('boundary', ['http', 'sse', 'history'])
@pytest.mark.parametrize('claims', [
    [{}],
    [{'text': '주장'}],
    [{'text': None, 'citations': CLAIMS[0]['citations']}],
    [{'text': 7, 'citations': CLAIMS[0]['citations']}],
    [{'text': '', 'citations': CLAIMS[0]['citations']}],
    [{'text': '주장', 'citations': None}],
    [{'text': '주장', 'citations': []}],
    [{'text': '주장', 'citations': [{}]}],
    [{'text': '주장', 'citations': [{'evidence_id': 'law-1'}]}],
    [{'text': '주장', 'citations': [{'evidence_id': '', 'quote': '원문'}]}],
    [{'text': '주장', 'citations': [{'evidence_id': 1, 'quote': '원문'}]}],
    [{'text': '주장', 'citations': [{'evidence_id': 'law-1', 'quote': False}]}],
    [{'text': '주장', 'citations': [{'evidence_id': 'law-1', 'quote': ''}]}],
    [{'text': '주장', 'citations': [{'evidence_id': 'law-1', 'quote': '가' * 2401}]}],
])
def test_invalid_claims_fail_at_response_boundary(boundary, claims, monkeypatch):
    with pytest.raises(api.BackendClientError) as captured:
        read_result(boundary, {**RAW, 'cited_claims': deepcopy(claims)}, monkeypatch)
    assert captured.value.code == 'CONTRACT_MISMATCH'


@pytest.mark.parametrize('boundary', ['http', 'sse', 'history'])
@pytest.mark.parametrize('claims', [None, [], CLAIMS])
def test_valid_claims_and_legacy_results_keep_json_shape(boundary, claims, monkeypatch):
    payload = deepcopy(RAW)
    if claims is not None:
        payload['cited_claims'] = deepcopy(claims)
    original = deepcopy(payload)
    result = read_result(boundary, payload, monkeypatch)
    assert result['cited_claims'] == (claims or [])
    assert payload == original
