import json,subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import imageio_ffmpeg

root=Path('C:/dev/aio-01-p2-team2/tmp/video_review')
out=Path('C:/dev/aio-01-p2-team2/output/video');out.mkdir(parents=True,exist_ok=True)
clips=json.loads((root/'clips.json').read_text(encoding='utf-8'))
ff=imageio_ffmpeg.get_ffmpeg_exe()
# Source-relative seconds. Keep actual output screens, omit typing/correction and
# long cursor-only navigation. All retained material plays at original speed.
keep={
0:[(0,8),(26,30.5),(49.3,55.5)],
1:[(1,16),(19,40),(42,77),(91,108.2)],
2:[(1,14),(58,83),(102,119),(130,150)],
3:[(1,30),(40,46.8)],
4:[(0,6),(18,31),(34,72),(76,104),(109,114)],
5:[(1,14),(39,61),(68,80),(91,99.3)],
6:[(1,14.7)]}

def render(i):
    ranges=keep[i];n=len(ranges);filters=[]
    filters.append('[0:v]split='+str(n)+''.join(f'[v{j}]' for j in range(n)))
    filters.append('[0:a]asplit='+str(n)+''.join(f'[a{j}]' for j in range(n)))
    for j,(s,e) in enumerate(ranges):
        filters += [f'[v{j}]trim=start={s}:end={e},setpts=PTS-STARTPTS,fps=30,setsar=1[vv{j}]',
                    f'[a{j}]atrim=start={s}:end={e},asetpts=PTS-STARTPTS,aresample=48000[aa{j}]']
    filters.append(''.join(f'[vv{j}][aa{j}]' for j in range(n))+f'concat=n={n}:v=1:a=1[vout][aout]')
    path=root/f'edited-{i}.mp4'
    with (root/f'encode-{i}.log').open('w') as log:
        subprocess.run([ff,'-hide_banner','-y','-threads','2','-i',clips[i]['path'],'-filter_complex_threads','1','-filter_complex',';'.join(filters),
            '-map','[vout]','-map','[aout]','-c:v','libx264','-preset','veryfast','-crf','20','-threads','3','-pix_fmt','yuv420p',
            '-c:a','aac','-b:a','128k','-movflags','+faststart',str(path)],stdout=log,stderr=log,check=True)
    print('finished clip',i,flush=True)
    return path

with ThreadPoolExecutor(max_workers=2) as pool:paths=list(pool.map(render,range(len(clips))))
lst=root/'concat.txt';lst.write_text('\n'.join(f"file '{p.as_posix()}'" for p in paths),encoding='utf-8')
final=out/'LawPath_시연_편집본.mp4'
subprocess.run([ff,'-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(lst),'-c','copy','-movflags','+faststart',str(final)],check=True)
duration=sum(e-s for ranges in keep.values() for s,e in ranges)
notes=['# LawPath 시연 영상 편집 기록','',f'원본 프로젝트: 팀플.mepj',f'원본 약 638.865초 → 편집본 약 {duration:.1f}초','',
'원본 영상 및 프로젝트는 변경하지 않았습니다. 영상과 오디오는 같은 구간으로 잘랐으며, 재생 속도는 변경하지 않았습니다.',
'커서가 영상에 합성되어 있어 커서 자체의 궤적을 수정하지 않고, 불필요한 이동과 입력 수정 구간을 컷 편집했습니다.',
'비회원 임대차 영상 끝의 잘못 입력한 용어 질문 및 해당 답변 구간은 제외했습니다.','',
'## 보존 구간 (각 원본 파일 기준 초)']
for i,clip in enumerate(clips):notes.append(f'- {Path(clip["path"]).name}: '+', '.join(f'{s:g}-{e:g}' for s,e in keep[i]))
(out/'편집_기록.md').write_text('\n'.join(notes),encoding='utf-8')
print('OUTPUT',final,'duration',duration,flush=True)
