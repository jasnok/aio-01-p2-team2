import pytest
from streamlit.testing.v1 import AppTest

from frontend.clients import backend_client as api
from frontend.clients.agent_stream import final_result
from frontend.services.api_legal_service import ApiLegalService
from frontend.components.stream_analysis import friendly_event


def payload(assessment=None):
    stopped = assessment and assessment.get('status') == 'needs_clarification'
    return dict(request_id='q1', agent_id='consumer', status='stopped' if stopped else 'completed',
                termination_reason='needs_clarification' if stopped else 'model_finished',
                question_summary='요약', answer='안내', is_mock=False,
                follow_up_questions=['어떤 문제가 발생했나요?'], input_assessment=assessment)


@pytest.mark.parametrize('status', [None, 'sufficient', 'proceed_with_caution', 'needs_clarification'])
def test_sync_and_sse_preserve_assessment(monkeypatch, status):
    raw = payload({'status': status, 'message': '판단 안내'} if status else None)
    monkeypatch.setattr(api, '_request', lambda *a, **kw: raw)
    sync = api.ask_legal_question('consumer', '질문 내용입니다', 's1')
    streamed = final_result(dict(run_id='r1', status=raw['status'], result=raw), 'r1')
    for result in [sync, streamed]:
        adapted = ApiLegalService.adapt_analysis(result, '질문 내용입니다')
        assert adapted['input_assessment'] == raw['input_assessment']
        if status == 'needs_clarification':
            assert adapted['result_state'] == 'needs_clarification'
    raw.pop('input_assessment')
    assert api.ask_legal_question('consumer', '질문 내용입니다', 's1')['input_assessment'] is None


@pytest.mark.parametrize('assessment', [[], 'bad', {'status': 'bad', 'message': '안내'},
                                       {'status': 'sufficient', 'message': 3}])
def test_invalid_contract_rejected(monkeypatch, assessment):
    raw = payload()
    raw['input_assessment'] = assessment
    monkeypatch.setattr(api, '_request', lambda *a, **kw: raw)
    with pytest.raises(api.BackendClientError, match='계약'):
        api.ask_legal_question('consumer', '질문 내용입니다', 's1')
    with pytest.raises(api.BackendClientError, match='계약'):
        final_result(dict(run_id='r1', status='completed', result=raw), 'r1')


@pytest.mark.parametrize('status', ['sufficient', 'proceed_with_caution', 'needs_clarification'])
def test_assessment_ui(status):
    result = ApiLegalService.adapt_analysis(payload({'status': status, 'message': '판단 안내'}), '질문')
    app = AppTest.from_string('from frontend.components.answer_view import render_analysis_result\n'
                              f'render_analysis_result({ascii(result)})').run()
    assert not app.exception
    notices = app.info if status == 'sufficient' else app.warning
    assert sum(x.value == '판단 안내' for x in notices) == 1
    if status == 'needs_clarification':
        assert not app.expander
        assert sum(x.value == '어떤 문제가 발생했나요?' for x in app.text) == 1
        assert not any('관련 법령' in x.value for x in app.markdown)


def test_quality_removed_and_minimum_preserved():
    app = AppTest.from_string('import streamlit as st\n'
        'from frontend.components.question_form import render_question_form\n'
        'st.session_state.setdefault("analysis_in_progress", False)\n'
        'render_question_form("consumer")').run()
    assert not any('입력 품질' in x.value or '/4' in x.value for x in (*app.caption, *app.markdown))
    app.text_area[0].set_value('짧음').run()
    app.button[1].click().run()
    assert '5자 이상' in app.warning[0].value


def test_validation_message_hides_raw_text():
    for event in ['step.started', 'step.completed']:
        msg = friendly_event(event, {'stage': 'validation', 'message': 'SECRET'})
        assert '질문 내용 확인' in msg and 'SECRET' not in msg


@pytest.mark.parametrize('long_input', [False, True])
def test_clarification_followup_combines_and_limits(long_input):
    original = '가' * 1998 if long_input else '원래 질문 내용입니다'
    app = AppTest.from_string('import streamlit as st\n'
        'from frontend.components.follow_up_chat import render_follow_up_chat\n'
        'class Service:\n'
        ' def analyze_case(self, category, question):\n'
        '  st.session_state.sent = question\n'
        '  return dict(request_id="next", answer="answer")\n'
        'st.session_state.setdefault("conversation_messages", [])\n'
        'st.session_state.setdefault("session_history", [])\n'
        f'render_follow_up_chat(dict(request_id="q1", agent_id="consumer", question={ascii(original)}, '
        'result_state="needs_clarification", follow_up_questions=["What happened?"]), Service())').run()
    assert not any((b.key or '').startswith('follow-suggestion') for b in app.button)
    assert app.text_input[0].label == '추가 정보'
    app.text_input[0].set_value('상품이 미배송되었습니다')
    next(b for b in app.button if b.label == '추가 정보로 다시 분석').click().run()
    assert not app.exception
    if long_input:
        assert '2000자' in app.warning[0].value
        assert 'sent' not in app.session_state
    else:
        assert app.session_state.sent == original + '\n추가 정보: 상품이 미배송되었습니다'
    app.run()
    app.button(key='new-analysis').click().run()
    assert app.session_state.last_result is None
