from __future__ import annotations
import argparse, json, subprocess
from pathlib import Path
from config import load_settings
from logging import get_logger, write_event
log=get_logger('voice')

def synthesize(script_text: str, job_id: str, output: str | None=None) -> Path:
    s=load_settings(); out=Path(output) if output else s.path('audio')/f'{job_id}.wav'; out.parent.mkdir(parents=True, exist_ok=True)
    ref_audio=s.root / s.get('voice.reference_audio'); ref_text=s.root / s.get('voice.reference_text')
    if not ref_audio.exists(): raise FileNotFoundError(f'Missing F5-TTS reference audio: {ref_audio}')
    if not ref_text.exists(): raise FileNotFoundError(f'Missing F5-TTS reference text: {ref_text}')
    tmp=s.path('temp')/f'{job_id}_raw.wav'; tmp.parent.mkdir(parents=True, exist_ok=True)
    cmd=[s.get('f5_tts.command','f5-tts_infer-cli'), '--ref_audio', str(ref_audio), '--ref_text', str(ref_text), '--gen_text', script_text, '--output_file', str(tmp)]
    subprocess.run(cmd, check=True)
    ff=[s.get('ffmpeg_path','ffmpeg'),'-y','-i',str(tmp),'-af',f"loudnorm=I={s.get('voice.normalize_lufs',-16)}:TP=-1.5:LRA=11",'-ar','48000','-ac','2',str(out)]
    subprocess.run(ff, check=True)
    write_event('voice_generated', {'job_id':job_id,'path':str(out)})
    return out

def main(queue='output/scripts.json'):
    for item in json.loads(Path(queue).read_text(encoding='utf-8')):
        synthesize(item['script'], str(item['id']))
if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--queue',default='output/scripts.json'); main(**vars(ap.parse_args()))
