import asyncio
import json
import sys
from types import SimpleNamespace

import pytest
from scripts import compare_latency, compare_reranking


@pytest.mark.parametrize('kind', ['latency', 'reranking'])
def test_existing_experiment_prevents_model_work(monkeypatch, tmp_path, kind):
    target = tmp_path / 'existing'
    if kind == 'latency':
        target.mkdir()
        original = target / 'case-0-baseline-1.json'
        original.write_bytes(b'old experiment\r\n')
        args = SimpleNamespace(output_dir=str(target), input='missing-input')
        def unexpected(*args):
            pytest.fail('existing output must be rejected before model work')
        monkeypatch.setattr(compare_latency, 'run_case', unexpected)
        with pytest.raises(FileExistsError):
            asyncio.run(compare_latency.compare(args))
    else:
        original = target
        original.write_bytes(b'old experiment\r\n')
        monkeypatch.setattr(sys, 'argv', ['rerank', '--model', 'synthetic', '--input', 'missing-input', '--output', str(target)])
        monkeypatch.setattr(compare_reranking, 'OpenAIProvider', lambda *args: pytest.fail('must not initialize provider'))
        with pytest.raises(SystemExit) as error:
            compare_reranking.main()
        assert error.value.code == 2
    assert original.read_bytes() == b'old experiment\r\n'


def test_new_reranking_output_records_each_completed_case(monkeypatch, tmp_path):
    source, target = tmp_path / 'input.json', tmp_path / 'new.json'
    rows = [dict(kind='natural', id=str(i), query='계약', variants={'base': dict(document_ids=['1'], titles=['제목'], chunks=['계약 내용입니다.'])}) for i in range(2)]
    source.write_text(json.dumps({'records': rows}), encoding='utf-8')
    calls = []
    class Provider:
        def __init__(self, *args):
            pass
        def generate_structured(self, system, payload, schema):
            assert len(json.loads(target.read_text(encoding='utf-8'))['records']) == len(calls)
            candidates = json.loads(payload)['candidates']
            calls.append(candidates)
            return SimpleNamespace(output={'ordered_candidate_ids': list(candidates)}, model='synthetic', usage={})
    monkeypatch.setattr(compare_reranking, 'OpenAIProvider', Provider)
    monkeypatch.setattr(sys, 'argv', ['rerank', '--model', 'synthetic', '--input', str(source), '--output', str(target), '--limit', '2'])
    compare_reranking.main()
    result = json.loads(target.read_text(encoding='utf-8'))
    assert len(result['records']) == 2 and len(calls) == 2
    assert all(row['label_status'] == 'pending_human_review' for row in result['records'])


def test_new_latency_experiment_keeps_raw_and_index(monkeypatch, tmp_path):
    source, folder = tmp_path / 'input.json', tmp_path / 'new'
    source.write_text(json.dumps([dict(category='housing', question='합성 질문', run={'result': dict(related_laws=[], similar_cases=[], consultations=[])})]), encoding='utf-8')
    monkeypatch.setattr(compare_latency, 'get_settings', lambda: SimpleNamespace(openai_model='synthetic'))
    monkeypatch.setattr(compare_latency.subprocess, 'check_output', lambda args, **kwargs: '' if '--porcelain' in args else 'test-commit')
    async def run_case(*args):
        return dict(elapsed_ms=1, known_tokens=0, status='completed', llm_used=False, generation_status='fallback', model_calls=[])
    async def close():
        pass
    monkeypatch.setattr(compare_latency, 'run_case', run_case)
    monkeypatch.setattr(compare_latency, 'close_async_clients', close)
    args = SimpleNamespace(input=str(source), output_dir=str(folder), scenarios=[0], variants=['baseline'], repeats=1, scope='answer', max_calls=4)
    assert asyncio.run(compare_latency.compare(args)) == 0
    index = json.loads((folder / 'index.json').read_text(encoding='utf-8'))
    assert index['runs'][0]['file'] == 'case-0-baseline-1.json'
    assert index['human_quality_review'] == 'pending'
    assert (folder / index['runs'][0]['file']).is_file()


def test_latency_cli_existing_directory_exits_before_input_read(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, 'argv', ['compare', '--output-dir', str(tmp_path), '--input', 'missing-input'])
    with pytest.raises(SystemExit) as error:
        compare_latency.main()
    assert error.value.code == 2
    assert list(tmp_path.iterdir()) == []
