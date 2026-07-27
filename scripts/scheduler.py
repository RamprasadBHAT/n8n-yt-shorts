from __future__ import annotations
import argparse, json, time, hashlib
from pathlib import Path
from rapidfuzz import fuzz
from tenacity import retry, stop_after_attempt, wait_exponential
from tqdm import tqdm
from config import load_settings
from logging import get_logger, write_event
from download_stock import download
from render_video import render
from generate_thumbnail import generate
from youtube_upload import upload
from voice import synthesize
log=get_logger('scheduler')

def key(t): return hashlib.sha256(t.lower().strip().encode()).hexdigest()[:16]
def used():
    s=load_settings(); p=s.root/s.get('dedupe.state_file'); p.parent.mkdir(exist_ok=True)
    return json.loads(p.read_text()) if p.exists() else []
def is_dup(topic, seen): return any(fuzz.token_set_ratio(topic, x['topic'])/100 >= load_settings().get('dedupe.similarity_threshold',.86) for x in seen)
def mark(topic):
    s=load_settings(); p=s.root/s.get('dedupe.state_file'); data=used(); data.append({'topic':topic,'id':key(topic),'ts':time.time()}); p.write_text(json.dumps(data,indent=2),encoding='utf-8')

def make_captions(job_id, script):
    s=load_settings(); p=s.path('captions')/f'{job_id}.srt'; ass=s.path('captions')/f'{job_id}.ass'
    words=script.split(); dur=40/max(len(words),1); t=0; lines=[]
    for i in range(0,len(words),5):
        start=t; end=min(39.9,t+dur*5); t=end
        fmt=lambda x:f"00:00:{int(x):02d},{int((x%1)*1000):03d}"
        lines.append(f"{i//5+1}\n{fmt(start)} --> {fmt(end)}\n{' '.join(words[i:i+5])}\n")
    p.write_text('\n'.join(lines),encoding='utf-8'); ass.write_text('[Script Info]\nScriptType: v4.00+\n[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\nStyle: Default,Arial,74,&H00FFFFFF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,5,0,2,60,60,210,1\n[Events]\n',encoding='utf-8')
    return p

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=30))
def process(item, upload_enabled=False):
    job_id=item.get('id') or key(item['title']); script=item['script']; audio=synthesize(script,job_id); caps=make_captions(job_id,script); media=download(item.get('keywords', item['title']), job_id); video=render(job_id,str(audio),str(caps),[str(m) for m in media]); thumb=generate(item['title'], job_id, str(media[0]) if media[0].suffix.lower() in {'.jpg','.png','.jpeg'} else None)
    vid=None
    if upload_enabled: vid=upload(str(video),str(thumb),item['title'],item.get('description',''), ','.join(item.get('hashtags',[])))
    mark(item['title']); write_event('job_complete', {'job_id':job_id,'youtube_id':vid}); return job_id

def main(queue='output/scripts.json', upload_enabled=False):
    items=json.loads(Path(queue).read_text(encoding='utf-8')); seen=used()
    for item in tqdm(items[:load_settings().get('videos_per_batch',10)]):
        if is_dup(item['title'], seen): log.info('Skipping duplicate: %s', item['title']); continue
        process(item, upload_enabled)
if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--queue',default='output/scripts.json'); ap.add_argument('--upload',action='store_true'); main(**vars(ap.parse_args()))
