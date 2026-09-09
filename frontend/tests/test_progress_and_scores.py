import pytest

from frontend.components.evidence_card import score_label
from frontend.components.stream_analysis import stage_progress
from frontend.services.api_legal_service import _case_view
from frontend.components.evidence_card import readable_text
from frontend.components.evidence_card import evidence_html


def test_html_paragraphs_preserve_and_escape():
    text = '법령명: 법 내용: ① 첫 항 1. 첫 호 1의2. 다음 호 (2) 판단 <개정 2026.1.20> <script>alert(1)</script>'
    rendered = evidence_html(text)
    assert rendered.count('<p ') >= 6
    assert 'white-space:pre-wrap' in rendered and 'line-height:1.95' in rendered
    assert '2026.1.20' in rendered
    assert '<script>' not in rendered and '&lt;script&gt;' in rendered
from frontend.components.stream_analysis import update_searches


def test_readability_preserves_words_and_dates():
    text = '법령명: 형법 조문: 제319조 내용: ①첫 항. ②둘째 항. <개정 1995.12.29> [1] 판시사항 질문: 질문입니다. 답변: 답변입니다.'
    formatted = readable_text(text)
    assert ''.join(formatted.split()) == ''.join(text.split())
    assert '\n\n①' in formatted and '\n\n②' in formatted
    assert '\n\n[1]' in formatted and '\n\n답변:' in formatted
    assert '1995.12.29' in formatted


def test_search_stages_independent_of_order_and_duplicates():
    searches = {}
    values = []
    for tool in ['search_cases', 'search_consultations', 'search_laws']:
        values.append(update_searches(searches, 'step.started', {'tool': tool}))
        values.append(update_searches(searches, 'step.completed', {'tool': tool}))
        assert update_searches(searches, 'step.completed', {'tool': tool}) == values[-1]
    assert values == sorted(values)
    assert len(searches) == 3 and set(searches.values()) == {'완료'}


@pytest.mark.parametrize('value,expected', [(None, '관련도 미제공'), (0, '검색 점수 0.000'),
    (0.8234, '검색 점수 0.823'), (1, '검색 점수 1.000'),
    (True, '관련도 미제공'), (float('nan'), '관련도 미제공'), (-1, '관련도 미제공')])
def test_score_label(value, expected):
    assert score_label(value) == expected


def test_missing_score_not_zero():
    assert _case_view({})['score'] is None
    assert _case_view({'score': 0})['score'] == 0


def test_progress_monotonic_and_not_completed_by_events():
    value = stage_progress(0, 'run.started', {})
    for event, data in [('step.completed', {'stage': 'retrieval'}),
                        ('step.started', {'stage': 'validation'}),
                        ('step.completed', {'stage': 'verification'}),
                        ('run.completed', {}), ('input.required', {}), ('run.failed', {})]:
        updated = stage_progress(value, event, data)
        assert value <= updated < 100
        assert stage_progress(updated, event, data) == updated
        value = updated
