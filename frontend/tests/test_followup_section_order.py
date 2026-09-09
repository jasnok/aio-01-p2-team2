import pytest
from streamlit.testing.v1 import AppTest


@pytest.mark.parametrize('state,questions', [('completed',['Follow-up']), ('completed',[]), ('needs_clarification',['Follow-up'])])
def test_followup_position_and_absence(state, questions):
    app = AppTest.from_string(
        'from frontend.components.answer_view import render_analysis_result\n'
        f'render_analysis_result({dict(answer="Answer", result_state=state, is_mock=False, follow_up_questions=questions)!r})'
    ).run()
    assert not app.exception
    sections = [e for e in app.expander if e.label == '추가로 확인할 내용']
    if state == 'needs_clarification' or not questions:
        assert not sections
    else:
        children = list(app.main.children.values())
        section = next(i for i,e in enumerate(children) if getattr(e,'label',None)=='추가로 확인할 내용')
        download = next(i for i,e in enumerate(children) if e.type=='download_button')
        answer = next(i for i,e in enumerate(children) if getattr(e,'value',None)=='Answer')
        assert answer < section < download
