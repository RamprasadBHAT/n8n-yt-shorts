from __future__ import annotations
import argparse, json, re, urllib.request, xml.etree.ElementTree as ET
from pathlib import Path
try:
    from rapidfuzz import fuzz
except Exception:
    class fuzz:
        @staticmethod
        def token_set_ratio(a, b):
            sa, sb = set(a.lower().split()), set(b.lower().split())
            return int(100 * len(sa & sb) / max(len(sa | sb), 1))
from config import load_settings
from logging import write_event

def rss(url):
    try:
        req=urllib.request.Request(url, headers={'User-Agent':'AIShortsFactory/1.0'}); txt=urllib.request.urlopen(req, timeout=20).read().decode('utf-8', 'ignore')
        root=ET.fromstring(txt); return [e.findtext('title','') for e in root.findall('.//item')]
    except Exception: return []
def candidates():
    topics=[]
    topics += rss('https://news.google.com/rss/search?q=AI%20technology&hl=en-US&gl=US&ceid=US:en')
    topics += rss('https://hnrss.org/frontpage')
    topics += rss('https://www.reddit.com/r/technology/.rss')
    cleaned=[re.sub(r'\s+',' ',t).strip() for t in topics if len(t.strip())>12]
    if not cleaned and Path('11_Config/topics.txt').exists():
        seeds=[x.strip() for x in Path('11_Config/topics.txt').read_text(encoding='utf-8').splitlines() if x.strip()]
        cleaned=[f'{seed} breakthrough creators should understand today' for seed in seeds]
    return cleaned
def dedupe(items, limit):
    out=[]; banned=set(Path('11_Config/banned_topics.txt').read_text(errors='ignore').lower().splitlines()) if Path('11_Config/banned_topics.txt').exists() else set()
    for t in items:
        if any(b and b in t.lower() for b in banned): continue
        if all(fuzz.token_set_ratio(t,x)<86 for x in out): out.append(t)
        if len(out)>=limit: break
    return out
def main(limit=10, output='output/topics.json'):
    topics=dedupe(candidates(), limit*3)[:limit]
    data=[{'id':str(i+1),'title':t,'angle':'Explain why this matters in under 40 seconds','keywords':t} for i,t in enumerate(topics)]
    Path(output).parent.mkdir(exist_ok=True); Path(output).write_text(json.dumps(data,indent=2),encoding='utf-8'); write_event('topics_generated',{'count':len(data)}); print(json.dumps(data,indent=2))
if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--limit',type=int,default=10); ap.add_argument('--output',default='output/topics.json'); main(**vars(ap.parse_args()))
