import argparse,json
from pathlib import Path
from voice import synthesize
ap=argparse.ArgumentParser(); ap.add_argument('--queue',default='output/scripts.json'); a=ap.parse_args()
for item in json.loads(Path(a.queue).read_text(encoding='utf-8')): synthesize(item['script'], item['id'])
