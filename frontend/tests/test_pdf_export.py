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


def test_pdf_links_citations_to_each_evidence_body_without_inventing_ids():
    result = {
        'is_mock': False,
        'generation_status': 'llm',
        'cited_claims': [{'text': '자료별로 확인하세요.', 'citations': [
            {'evidence_id': key, 'quote': f'인용 {key}'}
            for key in ('law-1', 'case-2', 'consultation-3')]}],
        'related_laws': [{'title': '동일 제목', 'evidence_id': 'law-1', 'content': '법령 본문'}],
        'similar_cases': [{'title': '동일 제목', 'evidence_id': 'case-2', 'content': '판례 본문'}],
        'consultations': [
            {'title': '동일 제목', 'evidence_id': 'consultation-3', 'content': '상담 본문'},
            {'title': '이전 자료', 'content': '식별자가 없는 본문'},
        ],
    }
    text = ''.join(page.extract_text() for page in PdfReader(BytesIO(build_analysis_pdf(result))).pages)
    for key, body in [('law-1', '법령 본문'), ('case-2', '판례 본문'), ('consultation-3', '상담 본문')]:
        assert f'근거 {key}: 인용 {key}' in text
        assert f'근거 ID: {key}' in text
        assert text.index(f'근거 ID: {key}') < text.index(body)
    assert text.count('근거 ID:') == 3
    assert '식별자가 없는 본문' in text


def test_pdf_preserves_literal_evidence_identifier_and_quote():
    key = 'law<&>-한글'
    quote = '금액 <100> & 조건'
    result = {'cited_claims': [{'text': '주장', 'citations': [{'evidence_id': key, 'quote': quote}]}],
              'related_laws': [{'title': '법령', 'evidence_id': key, 'content': quote}]}
    text = ''.join(page.extract_text() for page in PdfReader(BytesIO(build_analysis_pdf(result))).pages)
    assert f'근거 ID: {key}' in text
    assert f'근거 {key}: {quote}' in text
