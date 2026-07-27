from __future__ import annotations
import argparse, json, re, time, urllib.parse, xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable
import requests
try:
    from rapidfuzz import fuzz
except Exception:
    class fuzz:
        @staticmethod
        def token_set_ratio(a, b):
            sa, sb = set(a.lower().split()), set(b.lower().split())
            return int(100 * len(sa & sb) / max(len(sa | sb), 1))
from config import load_settings
from gemini_client import GeminiClient
from logging import get_logger, write_event
log = get_logger('research')

@dataclass
class Topic:
    id: str
    topic: str
    title: str
    source: str
    url: str
    score: float = 0.0
    angle: str = ''
    keywords: str = ''

def slug(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.lower().strip().encode()).hexdigest()[:16]

def clean(text: str) -> str:
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', text or '')).strip()

def rss_items(url: str, source: str) -> list[Topic]:
    headers={'User-Agent':'AIShortsFactory/1.0'}
    res=requests.get(url, headers=headers, timeout=30); res.raise_for_status()
    root=ET.fromstring(res.text)
    out=[]
    for item in root.findall('.//item')[:50]:
        title=clean(item.findtext('title',''))
        link=clean(item.findtext('link',''))
        if len(title) >= 12:
            out.append(Topic(slug(title), title, title, source, link, keywords=title))
    return out

def google_trends_daily() -> list[Topic]:
    url='https://trends.google.com/trends/trendingsearches/daily/rss?geo=US'
    return rss_items(url, 'google_trends')

def reddit(sub='technology') -> list[Topic]:
    return rss_items(f'https://www.reddit.com/r/{sub}/.rss', f'reddit_{sub}')

def hacker_news() -> list[Topic]:
    return rss_items('https://hnrss.org/frontpage', 'hacker_news')

def configured_rss() -> list[Topic]:
    settings=load_settings(); feeds=settings.get('research.rss_feeds', []) or []
    topics=[]
    for url in feeds:
        try: topics.extend(rss_items(url, 'rss'))
        except Exception as exc: log.warning('RSS feed failed %s: %s', url, exc)
    return topics

def banned_terms() -> list[str]:
    p=Path('11_Config/banned_topics.txt')
    return [x.strip().lower() for x in p.read_text(encoding='utf-8', errors='ignore').splitlines() if x.strip()] if p.exists() else []

def used_topics() -> list[str]:
    p=load_settings().root / load_settings().get('dedupe.state_file', 'state/used_topics.json')
    if not p.exists(): return []
    return [str(x.get('topic') or x.get('title') or '').lower() for x in json.loads(p.read_text(encoding='utf-8'))]

def dedupe(topics: Iterable[Topic]) -> list[Topic]:
    banned=banned_terms(); used=used_topics(); out=[]
    for t in topics:
        lower=t.title.lower()
        if any(b in lower for b in banned): continue
        if any(fuzz.token_set_ratio(lower, u)/100 >= 0.86 for u in used if u): continue
        if any(fuzz.token_set_ratio(lower, x.title.lower())/100 >= 0.86 for x in out): continue
        out.append(t)
    return out

def rank_with_gemini(topics: list[Topic], limit: int) -> list[Topic]:
    prompt_path=Path('prompts/research_prompt.txt')
    base=prompt_path.read_text(encoding='utf-8') if prompt_path.exists() else 'Rank topics for viral YouTube Shorts.'
    payload=[asdict(t) for t in topics[:60]]
    prompt=f"{base}\nReturn strict JSON array of exactly {limit} objects with id, topic, title, score, angle, keywords. Candidates:\n{json.dumps(payload, ensure_ascii=False)}"
    ranked=GeminiClient().generate_json(prompt, temperature=0.3)
    by_id={t.id:t for t in topics}
    out=[]
    for row in ranked:
        source=by_id.get(str(row.get('id','')))
        if not source and row.get('title'):
            source=Topic(slug(row['title']), row.get('topic', row['title']), row['title'], 'gemini', '', keywords=row.get('keywords',''))
        if source:
            source.score=float(row.get('score', source.score or 0))
            source.angle=str(row.get('angle', source.angle or ''))
            source.keywords=', '.join(row.get('keywords', [])) if isinstance(row.get('keywords'), list) else str(row.get('keywords', source.keywords))
            out.append(source)
    return dedupe(out)[:limit]

def collect() -> list[Topic]:
    funcs=[google_trends_daily, hacker_news, lambda: reddit('technology'), lambda: reddit('artificial'), configured_rss]
    topics=[]
    for fn in funcs:
        try: topics.extend(fn())
        except Exception as exc: log.warning('source failed: %s', exc)
    if not topics:
        raise RuntimeError('No research sources returned topics. Check network access or configure RSS feeds.')
    return dedupe(topics)

def main(limit: int=10, output: str='output/topics.json') -> None:
    topics=rank_with_gemini(collect(), limit)
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    data=[asdict(t) for t in topics]
    Path(output).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    write_event('topics_generated', {'count': len(data), 'output': output})
    print(json.dumps(data, indent=2, ensure_ascii=False))
if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--limit',type=int,default=10); ap.add_argument('--output',default='output/topics.json'); main(**vars(ap.parse_args()))
