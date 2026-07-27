from __future__ import annotations
import argparse, json, subprocess
from pathlib import Path
from config import load_settings
from logging import write_event

def render(job_id: str, audio: str, captions: str, media: list[str], output: str | None=None) -> Path:
    s=load_settings(); out=Path(output) if output else s.path('videos')/f'{job_id}.mp4'; out.parent.mkdir(exist_ok=True)
    concat=s.path('temp')/f'{job_id}_inputs.txt'
    concat.write_text(''.join(f"file '{Path(m).resolve().as_posix()}'\n" for m in media), encoding='utf-8')
    bg=s.path('temp')/f'{job_id}_bg.mp4'
    w,h,fps=s.get('rendering.width',1080),s.get('rendering.height',1920),s.get('rendering.fps',60)
    subprocess.run([s.get('ffmpeg_path','ffmpeg'),'-y','-f','concat','-safe','0','-stream_loop','-1','-i',str(concat),'-t',str(s.get('rendering.duration_seconds',40)),'-vf',f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={fps},zoompan=z='min(zoom+0.0008,1.08)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)',format=yuv420p",'-an',str(bg)], check=True)
    vf=f"subtitles='{Path(captions).resolve().as_posix()}':force_style='{s.get('rendering.subtitle_style')}'"
    subprocess.run([s.get('ffmpeg_path','ffmpeg'),'-y','-i',str(bg),'-i',audio,'-vf',vf,'-c:v','libx264','-preset','medium','-b:v',s.get('rendering.video_bitrate','8000k'),'-c:a','aac','-b:a',s.get('rendering.audio_bitrate','192k'),'-shortest',str(out)], check=True)
    write_event('video_rendered', {'job_id':job_id,'path':str(out)})
    return out
if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--job-id',required=True); ap.add_argument('--audio',required=True); ap.add_argument('--captions',required=True); ap.add_argument('--media',required=True,nargs='+'); ap.add_argument('--output'); print(render(**vars(ap.parse_args())))
