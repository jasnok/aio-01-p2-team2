import json,subprocess
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import imageio_ffmpeg
root=Path('C:/dev/aio-01-p2-team2/tmp/video_review');clips=json.loads((root/'clips.json').read_text(encoding='utf-8'))
ff=imageio_ffmpeg.get_ffmpeg_exe();font=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',18)
points={0:[6,8,10,24,26,28,30,32,34,36,38,40,42,44,46,48,50],1:[76,78,80,82,84,86,88,90,92,94,96,98],2:[14,16,18,28,30,32,50,52,54,56,58,60,62,64,82,84,96,98,100,102,104,106,120,130],4:[110,112,114,116,118,120,122,124,126,128,130,132,142,144,146,148,150,152],5:[12,14,16,18,20,22,36,38,40,42,44,46,58,60,62,64,66,68,70,72]}
for i,times in points.items():
    for page in range(0,len(times),6):
        sheet=Image.new('RGB',(1440,3*460),'#e9edf4');d=ImageDraw.Draw(sheet)
        for j,t in enumerate(times[page:page+6]):
            p=root/f'frame-{i}-{t}.png'
            subprocess.run([ff,'-hide_banner','-loglevel','error','-ss',str(t),'-i',clips[i]['path'],'-frames:v','1','-vf','scale=720:-1','-y',str(p)],check=True)
            im=Image.open(p);x=(j%2)*720;y=(j//2)*460
            sheet.paste(im,(x,y+28));d.text((x+6,y),f'clip {i} / {t}s',font=font,fill='black')
        sheet.save(root/f'detail-{i}-{page//6}.jpg')
    print('done',i,flush=True)
