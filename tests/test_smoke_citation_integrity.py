import copy
from urllib.error import HTTPError

import pytest

from scripts import portfolio_smoke
from scripts.benchmark_analysis import summarize


BASE = {
    'is_mock': False, 'generation_status': 'llm', 'answer': '원문에 근거한 설명',
    'related_laws': [{'evidence_id': 'law-1', 'content': '계약 종료 후 반환할 수 있습니다.'}],
    'similar_cases': [], 'consultations': [],
    'cited_claims': [{'text': '원문에 근거한 설명', 'citations': [{'evidence_id': 'law-1', 'quote': '계약 종료 후 반환'}]}],
    'diagnostics': {'citation_mode': 'spans'},
}


class Stream:
    def __enter__(self):
        return iter([b'id: 1\n', b'event: run.completed\n', b'data: {"status":"completed"}\n', b'\n'])
    def __exit__(self, *args):
        pass


def run(monkeypatch, final):
    def request(base, path, headers, body=None):
        if path == '/api/agent-runs':
            return {'run_id': 'run-1'}
        if 'Content-Type' not in headers:
            raise HTTPError(base + path, 404, 'not found', {}, None)
        return {'status': 'completed', 'result': final}
    monkeypatch.setattr(portfolio_smoke, 'request', request)
    monkeypatch.setattr(portfolio_smoke, 'urlopen', lambda *args, **kwargs: Stream())
    return portfolio_smoke.run_scenario('http://localhost:8000', 'housing', '합성 검증 질문')


def test_valid_citations_are_counted_as_success(monkeypatch):
    row = run(monkeypatch, copy.deepcopy(BASE))
    assert row['checks']['citation_integrity'] is True
    assert summarize([row])['successes'] == 1


@pytest.mark.parametrize('claims', [
    [], [{'text': '주장', 'citations': []}],
    [{'text': '주장', 'citations': [{'evidence_id': 'law-1', 'quote': ''}]}],
    [{'text': '주장', 'citations': [{'evidence_id': 'law-1', 'quote': ' '}]}],
    [{'text': '', 'citations': [{'evidence_id': 'law-1', 'quote': '계약'}]}],
    [{'text': ' ', 'citations': [{'evidence_id': 'law-1', 'quote': '계약'}]}],
    [{'text': '주장', 'citations': [{'evidence_id': 'missing', 'quote': '계약'}]}],
    [{'text': '주장', 'citations': [{'evidence_id': 'law-1', 'quote': '원문에 없는 내용'}]}],
    [{'text': '주장'}], [None],
    [{'text': '주장', 'citations': [None]}],
])
def test_invalid_claims_fail_without_vacuous_success(monkeypatch, claims):
    final = copy.deepcopy(BASE)
    final['cited_claims'] = claims
    row = run(monkeypatch, final)
    assert 'error' not in row
    assert row['checks']['citation_integrity'] is False
    assert summarize([row])['successes'] == 0


def test_conflicting_duplicate_evidence_id_fails(monkeypatch):
    final = copy.deepcopy(BASE)
    final['similar_cases'] = [{'evidence_id': 'law-1', 'content': '계약 종료 후 반환이라는 다른 원문'}]
    row = run(monkeypatch, final)
    assert row['checks']['citation_integrity'] is False
    assert summarize([row])['successes'] == 0

@pytest.mark.parametrize('evidence', [None, {}, [None], [{'evidence_id': 'law-1', 'content': ''}], [{'evidence_id': [], 'content': '계약'}]])
def test_malformed_evidence_is_reported_as_failed_check(monkeypatch, evidence):
    final = copy.deepcopy(BASE)
    final['related_laws'] = evidence
    row = run(monkeypatch, final)
    assert 'error' not in row
    assert row['checks']['citation_integrity'] is False
    assert summarize([row])['successes'] == 0


def test_one_valid_claim_cannot_hide_an_uncited_claim(monkeypatch):
    final = copy.deepcopy(BASE)
    final['cited_claims'].append({'text': '추가 주장', 'citations': []})
    row = run(monkeypatch, final)
    assert row['checks']['citation_integrity'] is False


def test_identical_duplicate_source_is_unambiguous(monkeypatch):
    final = copy.deepcopy(BASE)
    final['similar_cases'] = copy.deepcopy(final['related_laws'])
    row = run(monkeypatch, final)
    assert row['checks']['citation_integrity'] is True
    assert summarize([row])['successes'] == 1
