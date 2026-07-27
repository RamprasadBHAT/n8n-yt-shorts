from __future__ import annotations
import argparse, json, hashlib, time
from pathlib import Path
from rapidfuzz import fuzz
from tenacity import retry, stop_after_attempt, wait_exponential
from tqdm import tqdm
from config import load_settings
from logging import get_logger, write_event
from voice import synthesize
from subtitles import estimate_captions
from download_stock import download
from render_video import render
from generate_thumbnail import generate
from youtube_upload import upload, scheduled_time
log=get_logger('scheduler')

def key(text: str) -> str: return hashlib.sha256(text.lower().strip().encode()).hexdigest()[:16]
def used() -> list[dict]:
    s=load_settings(); p=s.root/s.get('dedupe.state_file','state/used_topics.json'); p.parent.mkdir(parents=True, exist_ok=True)
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else []
def is_dup(topic: str, seen: list[dict]) -> bool:
    threshold=load_settings().get('dedupe.similarity_threshold',0.86)
    return any(fuzz.token_set_ratio(topic, str(x.get('topic','')))/100 >= threshold for x in seen)
def mark(topic: str, job_id: str) -> None:
    s=load_settings(); p=s.root/s.get('dedupe.state_file','state/used_topics.json'); data=used(); data.append({'topic':topic,'id':job_id,'ts':time.time()}); p.write_text(json.dumps(data,indent=2),encoding='utf-8')

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30))
def process(item: dict, upload_enabled: bool=False, index: int=0) -> str:
    job_id=str(item.get('id') or key(item['title']))
    audio=synthesize(item['script'], job_id)
    srt, _ass, _words=estimate_captions(job_id, item['script'])
    media=download(item.get('keywords') or item.get('title') or item.get('topic'), job_id)
    video=render(job_id, str(audio), str(srt), [str(m) for m in media])
    thumb=generate(item['title'], job_id)
    youtube_id=None
    if upload_enabled:
        youtube_id=upload(str(video), str(thumb), item['title'], item.get('description',''), ','.join(item.get('hashtags',[])), scheduled_time(index))
    mark(item.get('topic') or item['title'], job_id)
    write_event('job_complete', {'job_id':job_id,'youtube_id':youtube_id})
    return job_id

def main(queue='output/scripts.json', upload_enabled=False):
    items=json.loads(Path(queue).read_text(encoding='utf-8')); seen=used(); limit=load_settings().get('videos_per_batch',10)
    for idx,item in enumerate(tqdm(items[:limit])):
        topic=item.get('topic') or item.get('title')
        if is_dup(topic, seen): log.info('Skipping duplicate: %s', topic); continue
        process(item, upload_enabled, idx)
if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--queue',default='output/scripts.json'); ap.add_argument('--upload',action='store_true',dest='upload_enabled'); main(**vars(ap.parse_args()))
