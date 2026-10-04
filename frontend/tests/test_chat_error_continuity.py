import pytest
from types import SimpleNamespace
from streamlit.testing.v1 import AppTest


@pytest.mark.parametrize('question, original, request_count', [
    ('짧음', '원래 질문', 0), ('추가 정보가 충분합니다', '원' * 1999, 0),
    ('추가 정보가 충분합니다', '원래 질문', 1),
])
def test_clarification_errors_keep_messages_and_new_analysis(monkeypatch, question, original, request_count):
    from frontend.components import follow_up_chat
    monkeypatch.setattr(follow_up_chat, 'get_frontend_settings', lambda: SimpleNamespace(frontend_data_mode='mock', frontend_sse_enabled=False))
    app = AppTest.from_string(f'''
import streamlit as st
from frontend.core.session import initialize_session
from frontend.components.follow_up_chat import render_follow_up_chat
initialize_session()
if 'test_calls' not in st.session_state:
    st.session_state.test_calls = 0
    st.session_state.conversation_messages = [dict(role='user', content='이전 질문'), dict(role='assistant', content='이전 답변')]
class Service:
    def analyze_case(self, *args):
        st.session_state.test_calls += 1
        raise ValueError('분석에 실패했습니다.')
render_follow_up_chat(dict(result_state='needs_clarification', question={original!r}, agent_id='housing', request_id='original'), Service())
''').run()
    before = list(app.session_state['conversation_messages'])
    app.text_input[0].set_value(question)
    next(b for b in app.button if b.label == '추가 정보로 다시 분석').click().run()
    assert not app.exception
    assert app.error if request_count else app.warning
    assert app.session_state['test_calls'] == request_count
    assert app.session_state['conversation_messages'] == before
    assert len(app.chat_message) == 2
    assert app.text_input[0].value == question
    assert app.button(key='new-analysis')
    app.button(key='new-analysis').click().run()
    assert not app.exception
    assert not app.session_state['conversation_messages']


@pytest.mark.parametrize('question, request_count', [(' ', 0), ('한', 0), ('유효한 질문입니다', 1)])
def test_term_errors_keep_existing_messages(monkeypatch, question, request_count):
    from frontend.components import legal_terms_chat
    from frontend.clients import backend_client
    monkeypatch.setattr(legal_terms_chat, 'get_frontend_settings', lambda: SimpleNamespace(frontend_data_mode='api'))
    calls = []
    def chat(*args, **kwargs):
        calls.append(args)
        raise backend_client.BackendClientError('요청에 실패했습니다.')
    monkeypatch.setattr(backend_client, 'chat_legal_terms', chat)
    app = AppTest.from_string('''
import streamlit as st
from frontend.core.session import initialize_session
from frontend.components.follow_up_chat import render_follow_up_chat
initialize_session()
if 'test_seeded' not in st.session_state:
    st.session_state.test_seeded = True
    st.session_state.terms_identity = (st.session_state.auth_token, 'original', '원래 질문')
    st.session_state.terms_messages = [dict(role='user', content='이전 질문'), dict(role='assistant', content='이전 설명')]
    st.session_state.terms_conversation_id = 12
render_follow_up_chat(dict(request_id='original', question='원래 질문', result_state='completed'), None)
''').run()
    before = list(app.session_state['terms_messages'])
    app.text_area[0].set_value(question)
    next(b for b in app.button if b.label == '질문하기').click().run()
    assert not app.exception
    assert app.error if request_count else app.warning
    assert len(calls) == request_count
    assert app.session_state['terms_messages'] == before
    assert app.session_state['terms_conversation_id'] == 12
    assert len(app.chat_message) == 2
    assert app.text_area[0].value == question
    assert app.button(key='new-analysis')
