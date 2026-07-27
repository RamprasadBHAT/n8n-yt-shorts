from __future__ import annotations
import argparse, json
from pathlib import Path
from config import load_settings
from logging import write_event

def local_script(t):
    title=t['title'][:70]; hook=f"This could change everything: {title}."
    body=f"{hook} Here is the simple version. A new development is getting attention because it affects creators, developers, and everyday users. The key detail is not the headline, it is what happens next: faster tools, new risks, and a race to adapt. Watch this space, because the winners will be the people who understand it early."
    return {'id':t.get('id'), 'title':title, 'hook':hook, 'script':body, 'description':body+' Subscribe for daily AI and tech Shorts.', 'hashtags':['#AI','#Tech','#Shorts'], 'cta':'Follow for the next update.', 'visual_beats':['headline','problem','impact','future']}
def main(topics='output/topics.json', output='output/scripts.json'):
    items=json.loads(Path(topics).read_text(encoding='utf-8')); scripts=[local_script(x) for x in items]
    Path(output).write_text(json.dumps(scripts,indent=2),encoding='utf-8'); write_event('scripts_generated',{'count':len(scripts)}); print(json.dumps(scripts,indent=2))
if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--topics',default='output/topics.json'); ap.add_argument('--output',default='output/scripts.json'); main(**vars(ap.parse_args()))
