import argparse,json
from pathlib import Path
from download_stock import download
from render_video import render
ap=argparse.ArgumentParser(); ap.add_argument('--queue',default='output/scripts.json'); a=ap.parse_args()
for item in json.loads(Path(a.queue).read_text(encoding='utf-8')):
    jid=item['id']; media=download(item.get('keywords',item['title']),jid); render(jid, f'audio/{jid}.wav', f'captions/{jid}.srt', [str(m) for m in media])
