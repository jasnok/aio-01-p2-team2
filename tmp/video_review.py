import json, zipfile, subprocess
from pathlib import Path
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

ROOT=Path('C:/dev/aio-01-p2-team2/tmp/video_review')
ROOT.mkdir(parents=True,exist_ok=True)
FF=imageio_ffmpeg.get_ffmpeg_exe()
with zipfile.ZipFile('C:/Users/Playdata/OneDrive/Desktop/팀플.mepj') as z:
    config=json.loads(z.read('config.json'))
objects={}
def walk(x):
    if isinstance(x,dict):
        if '@meta' in x: objects[x['@meta']['object_id']]=x
        for v in x.values():walk(v)
    elif isinstance(x,list):
        for v in x:walk(v)
walk(config)
def resolve(x):return objects[x['@meta_reference']] if '@meta_reference' in x else x
clips=[]
for x in config['data']['timeline']['clips']:
    if 'timing' not in x:continue
    clip=resolve(x['clip']);timing=x['timing']
    if clip['type']!=1:continue
    file=resolve(clip['file'])
    clips.append(dict(path=file['path'],start=timing['sourcePosition']/1000,duration=timing['sourceDuration']/1000,timestamp=timing['timestamp']/1000))
clips.sort(key=lambda x:x['timestamp'])
(ROOT/'clips.json').write_text(json.dumps(clips,ensure_ascii=False,indent=2),encoding='utf-8')
font=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',16)
for i,clip in enumerate(clips):
    print(i,clip,flush=True)
    folder=ROOT/str(i);folder.mkdir(exist_ok=True)
    subprocess.run([FF,'-hide_banner','-loglevel','error','-ss',str(clip['start']),'-i',clip['path'],'-t',str(clip['duration']),'-vf','fps=1/8,scale=480:-1','-y',str(folder/'%03d.jpg')],check=True)
    frames=list(sorted(folder.glob('*.jpg')))
    for page in range(0,len(frames),12):
        sheet=Image.new('RGB',(1440,4*315),'#e9edf4');d=ImageDraw.Draw(sheet)
        for n,f in enumerate(frames[page:page+12]):
            im=Image.open(f);x=(n%3)*480;y=(n//3)*315
            sheet.paste(im,(x,y+28));d.text((x+6,y+3),f'{i} {Path(clip["path"]).name} | ~{(page+n)*8+4}s',font=font,fill='black')
        sheet.save(ROOT/f'sheet-{i}-{page//12}.jpg')
