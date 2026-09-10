from io import BytesIO
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor
from pypdf import PdfReader, PdfWriter

root = Path('C:/dev/aio-01-p2-team2/output/pdf')
pdfmetrics.registerFont(TTFont('K', 'C:/Windows/Fonts/malgun.ttf'))
pdfmetrics.registerFont(TTFont('KB', 'C:/Windows/Fonts/malgunbd.ttf'))
buffer = BytesIO()
c = canvas.Canvas(buffer, pagesize=(960, 540))
c.setFillColor(HexColor('#F7F9FD'))
c.rect(0, 0, 960, 540, fill=1, stroke=0)
c.setFillColor(HexColor('#EDF2FC'))
c.circle(942, 425, 209, fill=1, stroke=0)
c.setStrokeColor(HexColor('#D8E4F8'))
c.circle(942, 425, 154, fill=0, stroke=1)
c.circle(942, 425, 111, fill=0, stroke=1)
c.setFillColor(HexColor('#285FCA'))
c.roundRect(76, 447, 44, 5, 2.5, fill=1, stroke=0)
c.setFillColor(HexColor('#122F54'))
c.setFont('KB', 35)
c.drawString(76, 350, '“퇴직했는데 퇴직금을 못 받았습니다.”')

items = [
    ('01', '어떤 법을', '찾아야 하지?'),
    ('02', '어떤 판례를', '봐야 하지?'),
    ('03', '내 상황과', '비슷한 사례는?'),
]
for i, (number, first, second) in enumerate(items):
    x = 76 + i * 278
    c.setFillColor(HexColor('#FFFFFF'))
    c.setStrokeColor(HexColor('#D8E4F8'))
    c.roundRect(x, 113, 252, 166, 15, fill=1, stroke=1)
    c.setFillColor(HexColor('#285FCA'))
    c.setFont('KB', 14)
    c.drawString(x + 24, 246, number)
    c.setFillColor(HexColor('#354B66'))
    c.setFont('K', 22)
    c.drawString(x + 24, 202, first)
    c.setFillColor(HexColor('#122F54'))
    c.setFont('KB', 22)
    c.drawString(x + 24, 166, second)
    if i < 2:
        # Vector arrow keeps the sequence crisp at any zoom.
        c.setStrokeColor(HexColor('#285FCA'))
        c.setLineWidth(1.5)
        c.line(x + 257, 196, x + 273, 196)
        c.line(x + 268, 201, x + 273, 196)
        c.line(x + 268, 191, x + 273, 196)
c.save()
buffer.seek(0)
writer = PdfWriter()
writer.append(str(root / 'LawPath_발표용_표지.pdf'))
writer.append(PdfReader(buffer))
writer.add_metadata({'/Title': 'LawPath 발표 자료', '/Author': '2팀'})
output = root / 'LawPath_발표용.pdf'
with output.open('wb') as stream:
    writer.write(stream)
reader = PdfReader(output)
assert len(reader.pages) == 2
assert '퇴직했는데' in reader.pages[1].extract_text()
print(output)
