from pathlib import Path
from html import escape
import re
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor, white

ROOT = Path('C:/dev/aio-01-p2-team2')
OUT = ROOT / 'output/pdf/LawPath_발표_참고자료.pdf'
OUT.parent.mkdir(parents=True, exist_ok=True)
pdfmetrics.registerFont(TTFont('K', 'C:/Windows/Fonts/malgun.ttf'))
pdfmetrics.registerFont(TTFont('KB', 'C:/Windows/Fonts/malgunbd.ttf'))
source = Path('C:/Users/Playdata/Downloads/readme 기반 발표 자료.txt').read_text(encoding='utf-8-sig')
source = source.split('시연영상 - 8분')[0]
speeches = re.findall(r'코멘트\s*:\s*\(\s*(.*?)\s*\)', source, re.S)
assert len(speeches) == 4
speeches[0] = speeches[0].replace('실제 서비스 시연영상과 함께', '서비스의 구조와 처리 흐름을 중심으로')
W,H = 595.28,841.89
c = canvas.Canvas(str(OUT), pagesize=(W,H))
c.setTitle('LawPath 발표 참고자료')
c.setAuthor('LawPath 2팀')
navy = HexColor('#142D4E'); blue = HexColor('#2764CB'); gray = HexColor('#60718A')

def para(text,x,y,w,size=12,leading=21,color=navy,bold=False):
    p = Paragraph(text, ParagraphStyle('s',fontName='KB' if bold else 'K',fontSize=size,leading=leading,textColor=color,wordWrap='CJK'))
    _,h = p.wrap(w,1000)
    p.drawOn(c,x,y-h)
    return y-h

def header(n,title,time):
    c.setFillColor(blue); c.rect(0,H-10,W,10,fill=1,stroke=0)
    para('LawPath  /  발표자 참고자료',42,H-36,420,10,15,color=gray)
    para(f'{n:02d}  {title}',42,H-68,510,25,34,bold=True)
    para(time,42,H-109,510,10,16,color=gray)
    c.setStrokeColor(HexColor('#DDE5EF')); c.line(42,48,W-42,48)
    para('2팀 · 장상옥 / 임다혁 / 오병훈 / 박지혜',42,36,440,8,12,color=gray)
    para(f'{n} / 4',W-74,36,40,8,12,color=gray)

def box(lines,y=685):
    height = 30 + len(lines)*29
    c.setFillColor(HexColor('#F0F5FC')); c.roundRect(42,y-height,511,height,10,fill=1,stroke=0)
    pos = y-14
    for line in lines:
        pos=para(line,58,pos,479,12,19,bold=True)-10
    return y-height-25

def speech(n,y):
    y=para('발표 멘트',42,y,511,12,20,color=blue,bold=True)-13
    for part in re.split(r'\n\s*\n',speeches[n-1].strip()):
        y=para(escape(' '.join(part.split())),42,y,511,12,22)-14
    return y

header(1,'서비스 소개','예상 2분  ·  누적 0:00 - 2:00  ·  전체 원고 12분')
y=box(['LawPath','생활 속 법률 문제를 AI Agent가 분석하고','관련 근거를 찾아주는 서비스'])
y=speech(1,y)
para('발표 포인트',42,y-14,511,11,18,color=blue,bold=True)
para('서비스 이름과 목적을 먼저 전달한 뒤, 다음 장의 사용자 문제로 연결합니다.',42,y-40,511,11,19)
c.showPage()

header(2,'문제 정의','예상 3분  ·  누적 2:00 - 5:00')
y=box(['“퇴직했는데 퇴직금을 못 받았습니다.”','어떤 법을 찾아야 하지? → 어떤 판례를 봐야 하지?','→ 내 상황과 비슷한 사례는?'])
y=speech(2,y)
para('핵심 메시지',42,y-8,511,11,18,color=blue,bold=True)
para('사용자가 법률 검색어를 몰라도 자신의 상황을 자연어로 입력할 수 있도록 합니다.',42,y-34,511,11,19)
c.showPage()

header(3,'시스템 아키텍처','예상 3분  ·  누적 5:00 - 8:00')
y=box(['사용자 → Streamlit Frontend','HTTP → FastAPI Backend / Agent Runtime','MCP → Legal MCP / Search Tools','PostgreSQL + pgvector → 법률 검색 결과 반환'])
y=speech(3,y)
para('발표자 참고',42,y-5,511,11,18,color=blue,bold=True)
para('이 경로는 법률 자료 검색 기준입니다. 회원·질의 이력 등 일반 서비스 데이터 처리와 구분해 설명합니다.',42,y-29,511,10,17,color=gray)
c.showPage()

header(4,'Agent의 처리 흐름','예상 4분  ·  누적 8:00 - 12:00')
y=box(['질문 확인 → 필요한 정보와 검색 가능 여부 판단','정보 보완이 필요하면 → 추가 질문 후 재분석','검색 진행 → Tool 선택 → MCP 법령·판례·상담사례 검색','결과 확인 → 근거 기반 답변 및 제한사항 안내'])
y=speech(4,y)
para('코드 대조 메모',42,y-5,511,11,18,color=blue,bold=True)
y=para('로컬 develop 병합본 60fb526의 공통 Runtime은 Tool 선택, 결과 형식 확인, 근거 중복 제거 및 결과 부족 상태 구분을 수행합니다. 원고 도식의 “검색 조건 수정 → 자동 재검색”과 별도 “답변 검증” 단계는 이 Runtime에서 확인되지 않아 위 흐름도에서는 제외했습니다.',42,y-30,511,10,17,color=gray)
y=para('발표 전 실행 서버의 Agent 구현과 일치하는지 담당자에게 확인해 주세요. 이 자료는 실행 성공이나 성능 수치를 새로 검증한 보고서는 아닙니다.',42,y-10,511,10,17,color=gray)
para('참고: README.md · backend/app/agents/runtime.py',42,y-14,511,9,15,color=gray)
para('<link href="https://github.com/jasnok/aio-01-p2-team2" color="#2764CB">github.com/jasnok/aio-01-p2-team2</link>',42,y-34,511,9,15)
c.save()
print(OUT)
