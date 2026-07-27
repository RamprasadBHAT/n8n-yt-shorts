import argparse,json
from pathlib import Path
from youtube_upload import upload
ap=argparse.ArgumentParser(); ap.add_argument('--queue',default='output/scripts.json'); a=ap.parse_args()
for item in json.loads(Path(a.queue).read_text(encoding='utf-8')): upload(f"videos/{item['id']}.mp4", f"thumbnails/{item['id']}.jpg", item['title'], item['description'], ','.join(item.get('hashtags',[])))
