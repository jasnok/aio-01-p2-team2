from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor

out=Path('C:/dev/aio-01-p2-team2/output/pdf/LawPath_발표용_표지.pdf')
out.parent.mkdir(parents=True,exist_ok=True)
pdfmetrics.registerFont(TTFont('K','C:/Windows/Fonts/malgun.ttf'))
pdfmetrics.registerFont(TTFont('KB','C:/Windows/Fonts/malgunbd.ttf'))
c=canvas.Canvas(str(out),pagesize=(960,540))
c.setTitle('LawPath - 생활 법률 AI Agent')
c.setAuthor('2팀 / 장상옥 · 임다혁 · 오병훈 · 박지혜')
c.setFillColor(HexColor('#F7F9FD'));c.rect(0,0,960,540,fill=1,stroke=0)
# Quiet geometric motif, kept clear of the presentation text.
c.setFillColor(HexColor('#EDF2FC'));c.circle(942,425,209,fill=1,stroke=0)
c.setStrokeColor(HexColor('#D8E4F8'));c.setLineWidth(1)
c.circle(942,425,154,fill=0,stroke=1)
c.circle(942,425,111,fill=0,stroke=1)
c.setFillColor(HexColor('#285FCA'));c.roundRect(76,447,44,5,2.5,fill=1,stroke=0)
c.setFont('KB',76);c.setFillColor(HexColor('#122F54'));c.drawString(72,325,'LawPath')
c.setFillColor(HexColor('#354B66'));c.setFont('K',23)
c.drawString(76,263,'생활 속 법률 문제를 AI Agent가 분석하고')
c.drawString(76,224,'관련 근거를 찾아주는 서비스')
c.setStrokeColor(HexColor('#D4DFEE'));c.setLineWidth(1);c.line(76,155,650,155)
c.setFillColor(HexColor('#285FCA'));c.setFont('KB',17);c.drawString(76,115,'2팀')
c.setFillColor(HexColor('#42546C'));c.setFont('K',19);c.drawString(76,76,'장상옥 · 임다혁 · 오병훈 · 박지혜')
c.save()
print(out)
