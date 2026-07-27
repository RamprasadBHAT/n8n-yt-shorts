from __future__ import annotations
import argparse, json, textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from config import load_settings
from logging import write_event

def font(size:int):
    for candidate in ['C:/Windows/Fonts/arialbd.ttf','C:/Windows/Fonts/arial.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf']:
        if Path(candidate).exists(): return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()

def generate(title: str, job_id: str, background: str | None=None) -> Path:
    s=load_settings(); out=s.path('thumbnails')/f'{job_id}.jpg'; out.parent.mkdir(parents=True, exist_ok=True)
    img=Image.open(background).convert('RGB').resize((1080,1920)) if background and Path(background).exists() else Image.new('RGB',(1080,1920),(18,18,30))
    img=img.filter(ImageFilter.GaussianBlur(1)); overlay=Image.new('RGBA', img.size, (0,0,0,95)); img=Image.alpha_composite(img.convert('RGBA'), overlay)
    d=ImageDraw.Draw(img); d.rectangle((0,0,1080,180), fill=(255,210,0,255)); d.text((55,42),'AI SHORTS', font=font(78), fill=(0,0,0))
    text='\n'.join(textwrap.wrap(title.upper(), 12)[:4]); d.rounded_rectangle((60,1120,1020,1710), radius=45, fill=(255,210,0,240)); d.multiline_text((100,1180), text, font=font(112), fill=(0,0,0), spacing=18)
    img.convert('RGB').save(out, quality=94); write_event('thumbnail_generated', {'job_id':job_id,'path':str(out)}); return out

def main(queue='output/scripts.json'):
    for item in json.loads(Path(queue).read_text(encoding='utf-8')):
        generate(item['title'], str(item['id']))
if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--queue',default='output/scripts.json'); ap.add_argument('--title'); ap.add_argument('--job-id');
    args=ap.parse_args(); generate(args.title,args.job_id) if args.title and args.job_id else main(args.queue)
