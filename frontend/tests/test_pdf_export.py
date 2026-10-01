from io import BytesIO
from pypdf import PdfReader
from frontend.components.pdf_export import build_analysis_pdf


def test_pdf_full_korean_content():
    result = dict(agent_id='consumer', is_mock=False, question='미배송 질문', answer='분석 답변 <안내>',
                  related_laws=[dict(title='관련 법령', content='① 법령 본문입니다.\n\n' * 150, score=0)],
                  similar_cases=[dict(title='판례', content='판례 전체 본문 끝')],
                  consultations=[dict(title='상담', content='상담 전체 본문 끝', source={'url': 'https://secret.test'})])
    pdf = build_analysis_pdf(result)
    reader = PdfReader(BytesIO(pdf))
    text = ''.join(page.extract_text() for page in reader.pages)
    assert len(reader.pages) > 1
    for expected in ['미배송 질문', '판례 전체 본문 끝', '상담 전체 본문 끝', '검색 점수 0.000']:
        assert expected in text
    assert 'secret.test' not in text


def test_pdf_empty_result():
    assert build_analysis_pdf({}).startswith(b'%PDF')


def test_pdf_preserves_generation_state_and_claim_citations():
    result = {'is_mock': False, 'generation_status': 'fallback', 'answer': '자료 안내',
              'cited_claims': [{'text': '확인할 주장', 'citations': [
                  {'evidence_id': 'law-1', 'quote': '검증된 원문 인용'}]}]}
    text = ''.join(page.extract_text() for page in PdfReader(BytesIO(build_analysis_pdf(result))).pages)
    assert '검색된 자료 목록을 대신 제공합니다' in text
    assert '확인할 주장' in text
    assert '검증된 원문 인용' in text
