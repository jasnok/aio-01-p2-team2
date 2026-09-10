from io import BytesIO
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor
from pypdf import PdfReader, PdfWriter
import math

root = Path('C:/dev/aio-01-p2-team2/output/pdf')
pdfmetrics.registerFont(TTFont('K', 'C:/Windows/Fonts/malgun.ttf'))
pdfmetrics.registerFont(TTFont('KB', 'C:/Windows/Fonts/malgunbd.ttf'))
b = BytesIO()
c = canvas.Canvas(b, pagesize=(960, 540))
navy, blue, gray = '#122F54', '#285FCA', '#42546C'
c.setFillColor(HexColor('#F7F9FD')); c.rect(0,0,960,540,fill=1,stroke=0)
c.setFillColor(HexColor('#EDF2FC')); c.circle(955,520,150,fill=1,stroke=0)
c.setFillColor(HexColor(blue)); c.roundRect(60,488,44,5,2.5,fill=1,stroke=0)
def text(x,y,s,size=15,color=gray,bold=False,center=False):
    c.setFillColor(HexColor(color)); c.setFont('KB' if bold else 'K',size)
    (c.drawCentredString if center else c.drawString)(x,y,s)
text(60,446,'질문에서 근거까지, LawPath의 분석 흐름',29,navy,True)
def box(x,y,w,h,title,lines=(),tint=False):
    c.setFillColor(HexColor('#EDF2FC' if tint else '#FFFFFF'))
    c.setStrokeColor(HexColor('#D8E4F8')); c.setLineWidth(1)
    c.roundRect(x,y,w,h,11,fill=1,stroke=1)
    text(x+w/2,y+h-27,title,17,navy,True,True)
    for i,line in enumerate(lines): text(x+w/2,y+h-50-i*19,line,12.5,gray,False,True)
def arrow(points,both=False):
    c.setStrokeColor(HexColor(blue)); c.setLineWidth(1.5)
    p=c.beginPath(); p.moveTo(*points[0])
    for point in points[1:]: p.lineTo(*point)
    c.drawPath(p)
    def head(a,z):
        angle=math.atan2(z[1]-a[1],z[0]-a[0])
        for offset in [-.55,.55]:
            c.line(z[0],z[1],z[0]-7*math.cos(angle+offset),z[1]-7*math.sin(angle+offset))
    head(points[-2],points[-1])
    if both: head(points[1],points[0])

box(60,330,180,75,'질문 입력',['Frontend · Streamlit'])
box(300,330,200,75,'입력 충분성 판단',['Backend · LLM'],True)
arrow([(240,367),(300,367)])
arrow([(500,367),(560,367)])
c.setFillColor(HexColor('#EDF2FC')); c.setStrokeColor(HexColor('#A8BEE6'))
p=c.beginPath(); p.moveTo(560,367); p.lineTo(630,409); p.lineTo(700,367); p.lineTo(630,325); p.close()
c.drawPath(p,fill=1,stroke=1)
text(630,361,'검색 가능?',16,navy,True,True)

box(755,257,155,75,'보완 질문',['검색 전 중단'])
arrow([(700,367),(832,367),(832,332)])
text(739,378,'아니요',12,blue)
box(535,230,190,75,'분야별 도구 선택',['Backend · 공통 Runtime'],True)
arrow([(630,325),(630,305)])
text(643,313,'예',12,blue)
box(535,105,190,86,'MCP 검색 서버',['법령 · 판례 · 상담사례','분야별 허용 도구 호출'])
arrow([(630,230),(630,191)])
box(765,105,155,86,'PostgreSQL',['pgvector','문서 · 청크 검색'])
arrow([(725,148),(765,148)],both=True)
box(285,105,210,86,'근거 기반 답변 생성',['LLM 응답 형식·근거 ID 검증','실패 시 대체 답변'],True)
arrow([(535,148),(495,148)])
box(60,105,180,86,'분석 결과 표시',['Frontend · Streamlit','답변 · 관련 근거'])
arrow([(285,148),(240,148)])
text(60,66,'진행 상태는 SSE로 전달 · 정보 보완 후에는 새 분석 실행',13,gray)
text(60,34,'소비자 분야: 법령 → 상담사례 → 판례  |  임대차·근로 분야: 판례 → 통합 문서 검색',11,gray)
text(920,34,'develop · 45e216e',10,gray,False,False) if False else None
c.save(); b.seek(0)
src = root / 'LawPath_발표용.pdf'
reader=PdfReader(src)
writer=PdfWriter()
for page in reader.pages[:2]: writer.add_page(page)
writer.append(PdfReader(b))
writer.add_metadata({'/Title':'LawPath 발표 자료','/Author':'2팀','/Subject':'시스템 아키텍처 · develop 45e216e'})
out=root/'LawPath_발표용_3페이지.pdf'
with out.open('wb') as f: writer.write(f)
assert len(PdfReader(out).pages)==3
print(out)
