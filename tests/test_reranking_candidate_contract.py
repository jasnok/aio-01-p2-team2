import copy
import json
import sys

import pytest
from scripts import compare_reranking

BASE = dict(kind='natural', id='test', query='계약', variants={'base': dict(document_ids=[1], titles=['제목'], chunks=['계약 내용입니다.'])})


@pytest.mark.parametrize('variant', [
    dict(document_ids=[1, 2], titles=['제목'], chunks=['계약 내용입니다.']),
    dict(document_ids=[1], titles=['제목', '누락'], chunks=['계약 내용입니다.']),
    dict(document_ids=[1], titles=['제목'], chunks=[]),
    dict(document_ids='1', titles=['제목'], chunks=['본문']),
    dict(document_ids=[True], titles=['제목'], chunks=['본문']),
    dict(document_ids=[0], titles=['제목'], chunks=['본문']),
    dict(document_ids=[1], titles=[' '], chunks=['본문']),
    dict(document_ids=[1], titles=['제목'], chunks=[None]),
    dict(document_ids=[], titles=[], chunks=[]),
])
def test_bad_candidates_fail_before_provider_initialization(monkeypatch, tmp_path, variant):
    row = copy.deepcopy(BASE)
    row['variants']['base'] = variant
    source, output = tmp_path / 'source.json', tmp_path / 'output.json'
    source.write_text(json.dumps({'records': [row]}), encoding='utf-8')
    monkeypatch.setattr(compare_reranking, 'OpenAIProvider', lambda *args: pytest.fail('invalid candidates must not call model'))
    monkeypatch.setattr(sys, 'argv', ['rerank', '--model', 'synthetic', '--input', str(source), '--output', str(output)])
    with pytest.raises(ValueError):
        compare_reranking.main()
    assert json.loads(output.read_text(encoding='utf-8'))['records'] == []


def test_identical_candidates_deduplicate_and_conflicting_title_fails():
    row = copy.deepcopy(BASE)
    row['variants']['other'] = copy.deepcopy(row['variants']['base'])
    assert len(compare_reranking.build_candidates(row)) == 1
    row['variants']['other']['titles'] = ['다른 제목']
    with pytest.raises(ValueError, match='identity conflict'):
        compare_reranking.build_candidates(row)


def test_valid_pooled_candidates_keep_all_ids_and_original_types():
    row = copy.deepcopy(BASE)
    row['variants']['other'] = dict(document_ids=['external-2'], titles=['다른 자료'], chunks=['계약과 관련된 다른 내용입니다.'])
    candidates = compare_reranking.build_candidates(row)
    assert [item['document_id'] for item in candidates.values()] == [1, 'external-2']
    assert all(item['excerpts'] for item in candidates.values())
