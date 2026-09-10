from pathlib import Path
from html import escape
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor

out = Path('C:/dev/aio-01-p2-team2/output/pdf/LawPath_시연_진행자료.pdf')
out.parent.mkdir(parents=True, exist_ok=True)
pdfmetrics.registerFont(TTFont('K','C:/Windows/Fonts/malgun.ttf'))
pdfmetrics.registerFont(TTFont('KB','C:/Windows/Fonts/malgunbd.ttf'))
c=canvas.Canvas(str(out),pagesize=(595.28,841.89))
c.setTitle('LawPath 시연 진행자료')
c.setAuthor('LawPath 2팀')
def text(s,y,size=12,color='#142D4E',bold=False):
    p=Paragraph(escape(s).replace('\n','<br/>'),ParagraphStyle('p',fontName='KB' if bold else 'K',fontSize=size,leading=size*1.7,textColor=HexColor(color),wordWrap='CJK'))
    _,h=p.wrap(499,1000);p.drawOn(c,48,y-h);return y-h-12
def page(n,title,time):
    c.setFillColor(HexColor('#2764CB'));c.rect(0,832,596,10,fill=1,stroke=0)
    text('LawPath / 시연자 진행자료',805,10,'#60718A')
    text(f'{n:02d}  {title}',768,24,bold=True)
    text(time,719,10,'#60718A')
    c.setStrokeColor(HexColor('#DDE5EF'));c.line(48,47,547,47)
    text(f'2팀 · 원본 시연 구간 기반 / 총 8분 권장 배분                                      {n} / 4',33,8,'#60718A')
def block(title,body,y):
    y=text(title,y,12,'#2764CB',True)
    return text(body,y)

page(1,'대표 질문과 진행 상태','0:00 - 2:30 / 질문 입력부터 결과 도착까지')
y=block('화면 조작','1. LawPath 홈에서 소비자·중고거래를 선택합니다.\n2. 내 사례 분석에서 대표 질문 불러오기를 누릅니다.\n3. 질문 내용을 확인하고 사례 분석하기를 누릅니다.\n4. 진행바와 법령·판례·상담사례 검색 안내를 보여줍니다.',676)
y=block('입력할 대표 질문','신용카드 일시불 결제 후 할부로 전환했는데 물건이 배송되지 않았습니다. 카드사에 할부항변권을 행사할 수 있나요?',y-5)
y=block('발표 멘트','“사용자는 법률 검색어 대신 자신의 상황을 입력합니다. 분석을 시작하면 Agent의 진행 상황을 확인할 수 있습니다. 내부 Tool 이름을 그대로 노출하지 않고, 사용자가 이해하기 쉬운 메시지로 바꾸어 보여주는 SSE 화면입니다.”',y-5)
block('진행 메모','진행 상태는 실제 수신된 이벤트에 따라 표시됩니다. 처리 중에는 분석 버튼을 반복해서 누르지 않고 결과를 기다립니다. 오류가 나면 화면의 안내를 설명하고, 준비된 시연 녹화가 있다면 해당 구간으로 전환합니다.',y-5)
c.showPage()

page(2,'유형별 검색 결과','2:30 - 4:00 / 법령·상담사례·판례 구분')
y=block('화면 조작','1. 분석 안내의 AI 답변을 짧게 읽습니다.\n2. 아래로 이동해 관련 법령·유사 판례·소비자원 상담사례 제목과 건수를 보여줍니다.\n3. 각 항목을 차례로 열어 검색된 자료를 확인합니다.',676)
y=block('목표 화면','관련 법령 3건 / 소비자원 상담사례 3건 / 유사 판례 3건\n총 9건은 대표 질문의 통합 목표이며, 실제 화면의 건수를 기준으로 설명합니다.',y-5)
y=block('발표 멘트','“하나의 질문에 대해 법령, 상담사례, 판례를 각각 검색하고 결과를 유형별로 구분해서 제공합니다. 검색 결과가 부족할 때 임의의 자료로 9건을 채우는 것이 아니라, 실제 검색된 결과만 보여주는 것이 중요합니다.”',y-5)
block('확인 포인트','상담사례와 법원 판례는 서로 다른 자료입니다. 검색 결과의 개수만으로 답변의 정확성을 단정하지 않고, 질문과 관련된 내용인지 함께 확인합니다.',y-5)
c.showPage()

page(3,'상세 내용 확인','4:00 - 5:30 / 접기와 펼치기')
y=block('화면 조작','1. 유사 판례를 열고 판례 한 건의 상세보기를 누릅니다.\n2. 사건번호·법원·선고일과 본문을 보여줍니다.\n3. 관련 법령에서 한 건을 열어 조문·본문을 확인합니다.\n4. 소비자원 상담사례에서 질문과 답변 내용을 보여줍니다.\n5. 확인이 끝난 항목은 접어 화면을 정리합니다.',676)
y=block('발표 멘트','“사용자가 제목만 보고 판단하지 않도록 필요한 경우 상세 내용을 확인할 수 있게 구성했습니다. 자료를 접었을 때는 간략하게 살펴보고, 펼치면 법령 본문이나 판례·상담사례의 내용을 읽을 수 있습니다.”',y-5)
y=block('검색 점수가 보일 때','“검색 점수는 관련 자료의 검색 순위를 정하는 값입니다. 법률 적용 가능성이나 답변 정확도를 뜻하는 비율은 아닙니다.”',y-5)
block('진행 메모','긴 본문 전체를 읽지 말고 질문과 연결되는 부분 한두 문장을 짚습니다. 원문 추출 과정의 띄어쓰기 문제가 보이면 원문 정제 개선 항목으로 설명합니다.',y-5)
c.showPage()

page(4,'정보 보완 후 재분석','5:30 - 8:00 / 부족한 질문과 구체적인 질문 비교')
y=block('첫 입력','환불이 안되고 있어요.',676)
y=block('화면 조작','1. 위 질문을 입력하고 사례 분석하기를 누릅니다.\n2. 실제 반환된 보완 안내와 추가로 확인할 내용을 보여줍니다.\n3. 아래 보완 질문으로 입력을 바꾸고 다시 분석합니다.',y-3)
y=block('보완하여 입력할 질문','무신사 사이트에 환불을 요청했는데 7일이 넘게 환불이 안되고 있어요.\n무신사 사이트 내에 환불 공지된 대로 7일 이내에 환불 요청을 하고 해당 상품을 반품했는데 처리가 안되고 있어요.',y-3)
y=block('발표 멘트','“필요한 정보가 부족하면 Agent가 어떤 정보를 더 확인해야 하는지 안내합니다. 상대방, 기간, 환불 요청과 반품 여부를 추가해서 다시 분석해 보겠습니다. 보완 전후의 답변과 검색 결과를 비교할 수 있습니다.”',y-3)
y=block('반환 상태에 맞춰 설명','보완 요청으로 중단되면 ‘검색 전 추가 정보를 요청했습니다’라고 설명합니다. 검색이 진행되었다면 ‘일반적인 안내와 함께 추가 확인 사항을 제시했습니다’라고 설명합니다. 중단 여부는 실제 화면·실행 상태로 확인합니다.',y-3)
text('마무리: “이처럼 자연어 질문을 관련 법률 자료와 연결하고, 부족한 정보는 보완할 수 있도록 구성했습니다.”',y-3,11)
c.save()
print(out)
