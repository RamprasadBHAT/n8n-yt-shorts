from __future__ import annotations
import argparse, json
from pathlib import Path
from gemini_client import GeminiClient
from logging import get_logger, write_event
log=get_logger('script_generator')
REQUIRED={'title','hook','script','description','hashtags','cta','visual_beats'}

def validate(item: dict) -> dict:
    missing=REQUIRED-set(item)
    if missing: raise RuntimeError(f'Gemini script response missing fields: {sorted(missing)}')
    words=str(item['script']).split()
    if not 85 <= len(words) <= 125:
        log.warning('Script word count is %s; expected approximately 40 seconds.', len(words))
    item['hashtags']=[h if str(h).startswith('#') else f'#{h}' for h in item.get('hashtags', [])]
    return item

def generate_for_topic(topic: dict, client: GeminiClient, prompt_template: str) -> dict:
    prompt=f"""{prompt_template}
Topic record:
{json.dumps(topic, ensure_ascii=False)}
Return one strict JSON object only. The script must be factual, original, safe for YouTube, and timed for about 40 seconds.
"""
    data=client.generate_json(prompt, temperature=0.8)
    if isinstance(data, list): data=data[0]
    data['id']=topic.get('id') or data.get('id')
    data['topic']=topic.get('topic') or topic.get('title')
    data['keywords']=topic.get('keywords','')
    return validate(data)

def main(topics='output/topics.json', output='output/scripts.json'):
    topic_data=json.loads(Path(topics).read_text(encoding='utf-8'))
    prompt_path=Path('prompts/script_prompt.txt')
    template=prompt_path.read_text(encoding='utf-8')
    client=GeminiClient()
    scripts=[generate_for_topic(t, client, template) for t in topic_data]
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(json.dumps(scripts, indent=2, ensure_ascii=False), encoding='utf-8')
    write_event('scripts_generated', {'count': len(scripts), 'output': output})
    print(json.dumps(scripts, indent=2, ensure_ascii=False))
if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--topics',default='output/topics.json'); ap.add_argument('--output',default='output/scripts.json'); main(**vars(ap.parse_args()))
