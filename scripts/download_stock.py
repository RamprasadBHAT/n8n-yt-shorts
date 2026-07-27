from __future__ import annotations
import argparse, os, shutil, requests
from pathlib import Path
from config import load_settings

def download(query: str, job_id: str) -> list[Path]:
    s=load_settings(); out=s.path('temp')/job_id; out.mkdir(parents=True, exist_ok=True)
    key=s.env(s.get('stock.api_key_env','PEXELS_API_KEY'))
    files=[]
    if key:
        r=requests.get('https://api.pexels.com/videos/search', params={'query':query,'per_page':5,'orientation':'portrait'}, headers={'Authorization':key}, timeout=30); r.raise_for_status()
        for i,v in enumerate(r.json().get('videos',[])):
            link=max(v.get('video_files',[]), key=lambda x:x.get('height',0)).get('link')
            if link:
                data=requests.get(link, timeout=120); data.raise_for_status(); p=out/f'stock_{i}.mp4'; p.write_bytes(data.content); files.append(p)
    if not files:
        for p in (s.root/s.get('stock.fallback_assets_dir','assets/stock')).glob('*'):
            if p.suffix.lower() in {'.mp4','.mov','.jpg','.png','.jpeg'}:
                dest=out/p.name; shutil.copy2(p,dest); files.append(dest)
    if not files: raise RuntimeError('No stock media found; set PEXELS_API_KEY or add assets/stock media.')
    return files
if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('query'); ap.add_argument('job_id'); print('\n'.join(map(str, download(**vars(ap.parse_args())))))
