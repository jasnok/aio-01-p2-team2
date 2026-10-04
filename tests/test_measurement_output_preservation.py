import json
import sys
from types import SimpleNamespace

import pytest

from scripts import benchmark_analysis, portfolio_smoke


@pytest.mark.parametrize('kind', ['benchmark', 'smoke'])
def test_existing_measurement_is_preserved_before_any_work(monkeypatch, tmp_path, kind):
    folder = tmp_path / 'existing'
    folder.mkdir()
    raw = folder / 'run-1.json'
    summary = folder / 'summary.json'
    raw.write_bytes(b'previous raw evidence\r\n')
    summary.write_bytes(b'previous summary\r\n')
    def unexpected(*args, **kwargs):
        pytest.fail('existing output must be rejected before network, cache or child execution')
    monkeypatch.setattr(benchmark_analysis.subprocess, 'run', unexpected)
    monkeypatch.setattr(benchmark_analysis.subprocess, 'check_output', unexpected)
    monkeypatch.setattr(portfolio_smoke, 'run_scenario', unexpected)
    monkeypatch.setitem(sys.modules, 'benchmark_cache', SimpleNamespace(cold_cache=unexpected, prime_cache=unexpected))
    argv = ['benchmark', '--output-dir', str(folder)] if kind == 'benchmark' else ['smoke', '--output', str(raw), '--cache-state', 'cold']
    monkeypatch.setattr(sys, 'argv', argv)
    with pytest.raises(SystemExit) as error:
        (benchmark_analysis.main if kind == 'benchmark' else portfolio_smoke.main)()
    assert error.value.code == 2
    assert raw.read_bytes() == b'previous raw evidence\r\n'
    assert summary.read_bytes() == b'previous summary\r\n'
    assert sorted(path.name for path in folder.iterdir()) == ['run-1.json', 'summary.json']


def test_existing_empty_directory_is_not_repurposed(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, 'argv', ['benchmark', '--output-dir', str(tmp_path)])
    with pytest.raises(SystemExit) as error:
        benchmark_analysis.main()
    assert error.value.code == 2
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('fail', [False, True])
def test_new_smoke_file_preserves_each_completed_sample(monkeypatch, tmp_path, fail):
    destination = tmp_path / 'new' / 'run.json'
    calls = []
    def scenario(base, category, question, require_llm):
        # The path is reserved before requests; previous completed rows are flushed.
        assert json.loads(destination.read_text(encoding='utf-8')) == calls
        row = {'category': category, 'elapsed_ms': 1, 'checks': {'synthetic': not fail}}
        calls.append(row)
        return row
    monkeypatch.setattr(portfolio_smoke, 'run_scenario', scenario)
    monkeypatch.setitem(sys.modules, 'benchmark_cache', SimpleNamespace(cold_cache=lambda: {}, prime_cache=lambda *args: {}))
    monkeypatch.setattr(sys, 'argv', ['smoke', '--output', str(destination), '--scenarios', '0', '1'])
    assert portfolio_smoke.main() == int(fail)
    records = json.loads(destination.read_text(encoding='utf-8'))
    assert len(records) == 2 and [row['scenario_index'] for row in records] == [0, 1]
    assert records == calls
    original = destination.read_bytes()
    with pytest.raises(SystemExit):
        portfolio_smoke.main()
    assert destination.read_bytes() == original


def test_concurrent_smoke_cannot_share_reserved_output(monkeypatch, tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    started, release = Event(), Event()
    calls = []
    destination = tmp_path / 'concurrent.json'
    def scenario(*args):
        calls.append(1)
        started.set()
        assert release.wait(5)
        return {'elapsed_ms': 1, 'checks': {'synthetic': True}}
    monkeypatch.setattr(portfolio_smoke, 'run_scenario', scenario)
    monkeypatch.setitem(sys.modules, 'benchmark_cache', SimpleNamespace(cold_cache=lambda: {}, prime_cache=lambda *args: {}))
    monkeypatch.setattr(sys, 'argv', ['smoke', '--output', str(destination), '--scenarios', '0'])
    with ThreadPoolExecutor(max_workers=1) as executor:
        running = executor.submit(portfolio_smoke.main)
        try:
            assert started.wait(2)
            with pytest.raises(SystemExit) as error:
                portfolio_smoke.main()
            assert error.value.code == 2
        finally:
            release.set()
        assert running.result(timeout=2) == 0
    assert calls == [1]
    assert len(json.loads(destination.read_text(encoding='utf-8'))) == 1
