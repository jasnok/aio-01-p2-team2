import pytest
from pydantic import ValidationError
from streamlit.testing.v1 import AppTest

from frontend.core.models import InputAssessmentView
from frontend.clients.agent_stream import final_result
from frontend.clients import backend_client as api
from frontend.services.api_legal_service import ApiLegalService
from frontend.tests.test_input_assessment import payload


CHECKS = dict(situation='met', timing='not_required', relationship='met', request_evidence='missing')


def test_zero_not_required_hidden():
    result = dict(agent_id='consumer', question='question', input_assessment=dict(
        status='proceed_with_caution', checks={**CHECKS, 'timing': 'met'}))
    app = render(result)
    assert '3/4' in app.markdown[0].value
    assert '해당 없음 0' not in app.markdown[0].value


def render(result, message='question', category='consumer'):
    return AppTest.from_string(
        'from frontend.components.input_checklist import render_input_checklist\n'
        f'render_input_checklist({category!r}, {message!r}, {ascii(result)})'
    ).run()


@pytest.mark.parametrize('status', ['sufficient', 'proceed_with_caution', 'needs_clarification'])
def test_backend_checks_display(status):
    result = dict(agent_id='consumer', question='question', input_assessment=dict(
        status=status, message='<script>unsafe</script>', checks=CHECKS))
    app = render(result)
    assert not app.exception
    text = app.markdown[0].value
    assert '2/3' in text and '해당 없음 1' in text
    assert '✓ 상대방·관계' in text and '○ 요청·증거' in text
    assert '<script>' not in text
    assert not app.caption


@pytest.mark.parametrize('result,message,category', [
    (None, 'question', 'consumer'),
    (dict(agent_id='consumer', question='question'), 'question', 'consumer'),
    (dict(agent_id='consumer', question='old'), 'question', 'consumer'),
    (dict(agent_id='housing', question='question'), 'question', 'consumer'),
])
def test_missing_or_stale_never_infers_checks(result, message, category):
    app = render(result, message, category)
    assert not app.exception and not app.markdown
    assert app.caption


@pytest.mark.parametrize('checks', [{}, {**CHECKS, 'timing': True}, {**CHECKS, 'timing': 'unknown'}])
def test_invalid_checks(checks):
    with pytest.raises(ValidationError):
        InputAssessmentView(status='sufficient', message='message', checks=checks)


def test_checks_survive_sync_sse_and_adapter(monkeypatch):
    raw = payload(dict(status='proceed_with_caution', message='message', checks=CHECKS))
    monkeypatch.setattr(api, '_request', lambda *args, **kwargs: raw)
    sync = api.ask_legal_question('consumer', 'question', 's1')
    sse = final_result(dict(run_id='r1', status='completed', result=raw), 'r1')
    for response in [sync, sse]:
        assert ApiLegalService.adapt_analysis(response, 'question')['input_assessment']['checks'] == CHECKS
