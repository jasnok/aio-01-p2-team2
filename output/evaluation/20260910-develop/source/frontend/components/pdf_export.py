"""In-memory PDF export; no additional agent calls or persistent user files."""
from datetime import datetime, timezone, timedelta
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph

from frontend.components.evidence_card import readable_text, score_label


def build_analysis_pdf(result: dict) -> bytes:
    font = 'LawPathKorean'
    if font not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(font, str(Path(__file__).parents[1] / 'assets/fonts/NanumGothic-Regular.ttf')))
    body = ParagraphStyle('body', fontName=font, fontSize=10, leading=18, spaceAfter=10, wordWrap='CJK')
    heading = ParagraphStyle('heading', parent=body, fontSize=14, leading=22, spaceBefore=14, keepWithNext=True)
    story = []

    def add(text, style=body):
        for part in readable_text(str(text or '없음')).split('\n\n'):
            if part.strip():
                story.append(Paragraph(escape(part.strip()).replace('\n', '<br/>'), style))

    add('LawPath 사례 분석 결과', heading)
    add('생성 시각: ' + datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M KST'))
    add('분야: ' + {'housing': '임대차·주거', 'labor': '근로·임금', 'consumer': '소비자·중고거래'}.get(result.get('agent_id'), '기타'))
    add(('DEMO 자료입니다. ' if result.get('is_mock', True) else '') + '이 문서는 참고 자료이며 법률 자문이나 판결 예측이 아닙니다.')
    for title, value in [('입력한 상황', result.get('question')), ('상황 요약', result.get('question_summary')),
                         ('핵심 쟁점', '\n\n'.join(result.get('key_issues', []))),
                         ('분석 안내', result.get('answer'))]:
        add(title, heading)
        add(value)
    assessment = result.get('input_assessment')
    if assessment:
        add('입력 판단 안내', heading)
        add(assessment.get('message'))
    for field, title in [('related_laws', '관련 법령'), ('similar_cases', '유사 판례'), ('consultations', '소비자원 상담사례')]:
        add(title, heading)
        items = result.get(field, [])
        if not items:
            add('표시할 자료가 없습니다.')
        for index, item in enumerate(items, 1):
            add(f"{index}. {item.get('title', '제목 없음')}", heading)
            info = [item.get('article') or item.get('article_number'), item.get('court'), item.get('case_number'), item.get('date') or item.get('decided_at')]
            add(' / '.join(str(v) for v in info if v) or '상세 식별 정보 미제공')
            add(score_label(item.get('score')))
            add(item.get('content') or item.get('detail') or item.get('summary') or item.get('result'))
    add('추가 확인 사항·주의사항', heading)
    for text in result.get('follow_up_questions', []) + result.get('cautions', []):
        add(text)
    add('검색 점수는 법률 적용 가능성이나 답변 정확도를 의미하지 않습니다.')
    output = BytesIO()

    def footer(canvas, doc):
        canvas.setFont(font, 9)
        canvas.drawRightString(A4[0] - 48, 26, f'LawPath / {doc.page}')

    SimpleDocTemplate(output, pagesize=A4, rightMargin=48, leftMargin=48,
                      topMargin=40, bottomMargin=48, title='LawPath 사례 분석 결과').build(
                          story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
