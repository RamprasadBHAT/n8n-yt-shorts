from __future__ import annotations
import argparse, textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from config import load_settings
from logging import write_event

def generate(title: str, job_id: str, background: str | None=None) -> Path:
    s=load_settings(); out=s.path('thumbnails')/f'{job_id}.jpg'; out.parent.mkdir(exist_ok=True)
    img=Image.open(background).convert('RGB').resize((1080,1920)) if background else Image.new('RGB',(1080,1920),(18,18,30))
    img=img.filter(ImageFilter.GaussianBlur(1)); overlay=Image.new('RGBA', img.size, (0,0,0,80)); img=Image.alpha_composite(img.convert('RGBA'), overlay)
    d=ImageDraw.Draw(img); font=ImageFont.truetype('arial.ttf', 118) if Path('C:/Windows/Fonts/arial.ttf').exists() else ImageFont.load_default()
    text='\n'.join(textwrap.wrap(title.upper(), 12)[:4]); d.rounded_rectangle((60,1180,1020,1710), radius=45, fill=(255,210,0,235)); d.multiline_text((100,1230), text, font=font, fill=(0,0,0), spacing=18)
    img.convert('RGB').save(out, quality=94); write_event('thumbnail_generated', {'job_id':job_id,'path':str(out)}); return out
if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('title'); ap.add_argument('job_id'); ap.add_argument('--background'); print(generate(**vars(ap.parse_args())))
