import argparse,json
from pathlib import Path
from scheduler import make_captions
ap=argparse.ArgumentParser(); ap.add_argument('--queue',default='output/scripts.json'); a=ap.parse_args()
for item in json.loads(Path(a.queue).read_text(encoding='utf-8')): print(make_captions(item['id'], item['script']))
