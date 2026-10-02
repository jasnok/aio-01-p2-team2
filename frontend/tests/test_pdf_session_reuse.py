from copy import deepcopy
from types import SimpleNamespace

import pytest

from frontend.components import result_export, pdf_export, follow_up_chat
from frontend.core import auth_session


class State(dict):
    def __setattr__(self, key, value):
        self[key] = value


def test_pdf_reuse_invalidates_on_content_change_and_retries_failed_generation(monkeypatch):
    state = State()
    calls, downloads = [], []

    def build(result):
        calls.append(deepcopy(result))
        if result.get('answer') == 'fail':
            raise RuntimeError('private content')
        return b'%PDF-' + result['answer'].encode()

    monkeypatch.setattr(pdf_export, 'build_analysis_pdf', build)
    monkeypatch.setattr(result_export, 'st', SimpleNamespace(session_state=state,
        download_button=lambda *a, **kw: downloads.append(kw['data']), warning=lambda *a: None))
    result = {'request_id': 'same', 'answer': 'first'}
    result_export.render_result_download(result)
    result_export.render_result_download(deepcopy(result))
    assert len(calls) == 1 and downloads == [b'%PDF-first'] * 2
    result['answer'] = 'changed'
    result_export.render_result_download(result)
    assert len(calls) == 2 and downloads[-1] == b'%PDF-changed'
    result['answer'] = 'fail'
    for _ in range(2):
        result_export.render_result_download(result)
        assert 'analysis_pdf_cache' not in state
    assert len(calls) == 4 and len(downloads) == 3


def test_pdf_bytes_are_never_shared_between_sessions(monkeypatch):
    calls = []
    monkeypatch.setattr(pdf_export, 'build_analysis_pdf', lambda result: calls.append(result) or b'%PDF')
    for state in (State(), State()):
        monkeypatch.setattr(result_export, 'st', SimpleNamespace(session_state=state,
            download_button=lambda *a, **kw: None))
        result_export.render_result_download({'answer': 'same'})
        result_export.render_result_download({'answer': 'same'})
        assert len(state) == 1
    assert len(calls) == 2


@pytest.mark.parametrize('module,clear', [(auth_session, auth_session.clear_private_state),
                                       (follow_up_chat, follow_up_chat._start_new_analysis)])
def test_identity_change_or_new_analysis_removes_pdf(monkeypatch, module, clear):
    state = State(analysis_pdf_cache=('digest', b'private PDF'))
    monkeypatch.setattr(module, 'st', SimpleNamespace(session_state=state))
    clear()
    assert 'analysis_pdf_cache' not in state
