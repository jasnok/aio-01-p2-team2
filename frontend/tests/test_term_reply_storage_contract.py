import pytest
from types import SimpleNamespace
from streamlit.testing.v1 import AppTest
from frontend.clients import backend_client

BASE = dict(request_id='term-result', answer='용어 설명', conversation_id=None, saved=False, storage='none')
BAD = [dict(conversation_id=value) for value in ('12', '', 'invalid', 0, -1, True, 1.0)] + [dict(saved=True), dict(saved=True, conversation_id=12), dict(saved=True, conversation_id=12, storage='guest_temporary')]


@pytest.mark.parametrize('changes', BAD)
def test_client_rejects_invalid_term_storage_reply(monkeypatch, changes):
    monkeypatch.setattr(backend_client, '_request', lambda *args, **kwargs: {**BASE, **changes})
    with pytest.raises(backend_client.BackendClientError) as error:
        backend_client.chat_legal_terms('member', 'guest-id', '용어 질문입니다')
    assert error.value.code == 'CONTRACT_MISMATCH'


@pytest.mark.parametrize('changes', [dict(), dict(conversation_id=12), dict(saved=True, conversation_id=12, storage='member'), dict(storage='guest_temporary')])
def test_client_accepts_valid_term_storage_reply(monkeypatch, changes):
    monkeypatch.setattr(backend_client, '_request', lambda *args, **kwargs: {**BASE, **changes})
    response = backend_client.chat_legal_terms('member', 'guest-id', '용어 질문입니다')
    assert response['conversation_id'] == changes.get('conversation_id')
    assert response['saved'] == changes.get('saved', False)


@pytest.mark.parametrize('changes', [dict(conversation_id='invalid'), dict(saved=True, conversation_id=12)])
def test_bad_reply_does_not_replace_chat_state(monkeypatch, changes):
    from frontend.components import legal_terms_chat
    monkeypatch.setattr(legal_terms_chat, 'get_frontend_settings', lambda: SimpleNamespace(frontend_data_mode='api'))
    monkeypatch.setattr(backend_client, '_request', lambda *args, **kwargs: {**BASE, **changes})
    app = AppTest.from_string('''
import streamlit as st
from frontend.core.session import initialize_session
from frontend.components.legal_terms_chat import render_legal_terms_chat
initialize_session()
if 'test_seeded' not in st.session_state:
    st.session_state.test_seeded = True
    st.session_state.terms_identity = (st.session_state.auth_token, 'analysis', '원래 질문')
    st.session_state.terms_messages = [dict(role='user', content='이전 질문'), dict(role='assistant', content='이전 설명')]
    st.session_state.terms_conversation_id = 7
render_legal_terms_chat(dict(request_id='analysis', question='원래 질문'))
''').run()
    before = list(app.session_state['terms_messages'])
    app.text_area[0].set_value('용어 질문입니다')
    next(button for button in app.button if button.label == '질문하기').click().run()
    assert not app.exception and app.error
    assert app.session_state['terms_messages'] == before
    assert app.session_state['terms_conversation_id'] == 7
    assert app.text_area[0].value == '용어 질문입니다'
    assert len(app.chat_message) == 2
