import json, subprocess
from pathlib import Path
import imageio_ffmpeg

root = Path('C:/dev/aio-01-p2-team2')
clips = json.loads((root/'tmp/video_review/clips.json').read_text(encoding='utf-8'))
listing = root/'tmp/video_review/full-concat.txt'
lines = ['ffconcat version 1.0']
for clip in clips:
    path = Path(clip['path'])
    assert path.is_file(), path
    lines += [f"file '{path.as_posix()}'", f"duration {clip['duration']}"]
listing.write_text('\n'.join(lines)+'\n', encoding='utf-8')
out = root/'output/video/LawPath_시연_원본통합_10분39초.mp4'
ff = imageio_ffmpeg.get_ffmpeg_exe()
with (root/'tmp/video_review/full-encode.log').open('w') as log:
    subprocess.run([ff,'-hide_banner','-n','-f','concat','-safe','0','-i',str(listing),
        '-map','0:v:0','-map','0:a:0','-vf','fps=30,setsar=1','-c:v','libx264',
        '-preset','veryfast','-crf','20','-threads','4','-pix_fmt','yuv420p',
        '-af','aresample=48000:async=1','-c:a','aac','-b:a','128k',
        '-movflags','+faststart',str(out)],stdout=log,stderr=log,check=True)
print('Export complete', out, flush=True)
result = subprocess.run([ff,'-hide_banner','-i',str(out),'-f','null','-'],capture_output=True,check=True)
for line in result.stderr.decode('utf-8',errors='replace').splitlines():
    if 'Duration:' in line or 'Stream #0:' in line:
        print(line,flush=True)
print('Full decode verified',flush=True)
subprocess.run([ff,'-hide_banner','-loglevel','error','-ss','630','-i',str(out),'-frames:v','1',
    '-vf','scale=960:-1','-y',str(root/'tmp/video_review/full-final.jpg')],check=True)
