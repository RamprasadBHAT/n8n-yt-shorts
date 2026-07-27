from __future__ import annotations
import argparse, json, subprocess
from pathlib import Path
from config import load_settings
from logging import write_event

def fmt(seconds: float) -> str:
    h=int(seconds//3600); m=int((seconds%3600)//60); s=int(seconds%60); ms=int((seconds%1)*1000)
    return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'

def estimate_captions(job_id: str, script: str, duration: float=40.0) -> tuple[Path,Path,Path]:
    settings=load_settings(); cap_dir=settings.path('captions'); cap_dir.mkdir(parents=True, exist_ok=True)
    words=script.split(); word_dur=duration/max(len(words),1)
    srt=cap_dir/f'{job_id}.srt'; ass=cap_dir/f'{job_id}.ass'; words_json=cap_dir/f'{job_id}_words.json'
    word_rows=[]; lines=[]
    for i,w in enumerate(words): word_rows.append({'word':w,'start':round(i*word_dur,3),'end':round((i+1)*word_dur,3)})
    for idx,start in enumerate(range(0,len(words),5),1):
        a=start*word_dur; b=min(duration,(start+5)*word_dur); text=' '.join(words[start:start+5])
        lines.append(f'{idx}\n{fmt(a)} --> {fmt(b)}\n{text}\n')
    srt.write_text('\n'.join(lines),encoding='utf-8')
    events=''.join(f"Dialogue: 0,{fmt(r['start']).replace(',', '.')},{fmt(r['end']).replace(',', '.')},Default,,0,0,0,,{r['word']}\\N\n" for r in word_rows)
    ass.write_text('[Script Info]\nScriptType: v4.00+\n[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\nStyle: Default,Arial,74,&H00FFFFFF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,5,0,2,60,60,210,1\n[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n'+events,encoding='utf-8')
    words_json.write_text(json.dumps(word_rows,indent=2),encoding='utf-8')
    write_event('subtitles_generated', {'job_id':job_id,'srt':str(srt),'ass':str(ass),'words':str(words_json)})
    return srt, ass, words_json

def main(queue='output/scripts.json'):
    items=json.loads(Path(queue).read_text(encoding='utf-8'))
    for item in items:
        estimate_captions(str(item['id']), item['script'])
if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--queue',default='output/scripts.json'); main(**vars(ap.parse_args()))
