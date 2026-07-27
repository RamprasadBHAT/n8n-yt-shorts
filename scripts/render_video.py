from __future__ import annotations
import argparse, json, subprocess
from pathlib import Path
from config import load_settings
from logging import write_event
from download_stock import download

def render(job_id: str, audio: str, captions: str, media: list[str], output: str | None=None) -> Path:
    s=load_settings(); out=Path(output) if output else s.path('videos')/f'{job_id}.mp4'; out.parent.mkdir(parents=True, exist_ok=True)
    if not Path(audio).exists(): raise FileNotFoundError(f'Missing audio file: {audio}')
    if not Path(captions).exists(): raise FileNotFoundError(f'Missing captions file: {captions}')
    if not media: raise RuntimeError('At least one visual media file is required')
    concat=s.path('temp')/f'{job_id}_inputs.txt'; concat.parent.mkdir(parents=True, exist_ok=True)
    concat.write_text(''.join(f"file '{Path(m).resolve().as_posix()}'\n" for m in media), encoding='utf-8')
    bg=s.path('temp')/f'{job_id}_bg.mp4'
    w,h,fps=s.get('rendering.width',1080),s.get('rendering.height',1920),s.get('rendering.fps',60)
    subprocess.run([s.get('ffmpeg_path','ffmpeg'),'-y','-f','concat','-safe','0','-stream_loop','-1','-i',str(concat),'-t',str(s.get('rendering.duration_seconds',40)),'-vf',f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={fps},zoompan=z='min(zoom+0.0008,1.08)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)',format=yuv420p",'-an',str(bg)], check=True)
    vf=f"subtitles='{Path(captions).resolve().as_posix()}':force_style='{s.get('rendering.subtitle_style')}'"
    subprocess.run([s.get('ffmpeg_path','ffmpeg'),'-y','-i',str(bg),'-i',audio,'-vf',vf,'-c:v','libx264','-preset','medium','-b:v',s.get('rendering.video_bitrate','8000k'),'-c:a','aac','-b:a',s.get('rendering.audio_bitrate','192k'),'-shortest',str(out)], check=True)
    write_event('video_rendered', {'job_id':job_id,'path':str(out)})
    return out

def main(queue='output/scripts.json'):
    for item in json.loads(Path(queue).read_text(encoding='utf-8')):
        jid=str(item['id']); media=download(item.get('keywords') or item.get('title') or item.get('topic'), jid)
        render(jid, f'audio/{jid}.wav', f'captions/{jid}.srt', [str(m) for m in media])
if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--queue',default='output/scripts.json'); main(**vars(ap.parse_args()))
