from __future__ import annotations
import argparse, json, datetime as dt
from pathlib import Path
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from config import load_settings
from logging import write_event
SCOPES=['https://www.googleapis.com/auth/youtube.upload']

def service():
    s=load_settings(); token=s.root/s.get('youtube.token_file'); secret=s.root/s.get('youtube.client_secret_file')
    if not secret.exists(): raise FileNotFoundError(f'Missing YouTube OAuth client secret: {secret}')
    creds=Credentials.from_authorized_user_file(token, SCOPES) if token.exists() else None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token: creds.refresh(Request())
        else: creds=InstalledAppFlow.from_client_secrets_file(secret, SCOPES).run_local_server(port=0)
        token.parent.mkdir(parents=True, exist_ok=True); token.write_text(creds.to_json(), encoding='utf-8')
    return build('youtube','v3',credentials=creds)

def scheduled_time(index:int) -> str | None:
    s=load_settings(); sched=s.get('youtube.schedule', {})
    if not sched.get('enabled', True): return None
    base=dt.datetime.now(dt.timezone.utc).replace(minute=0, second=0, microsecond=0) + dt.timedelta(hours=1 + index*int(sched.get('spacing_hours',4)))
    return base.isoformat().replace('+00:00','Z')

def upload(video, thumbnail, title, description, tags='', publish_at=None):
    s=load_settings(); body={'snippet':{'title':title[:100],'description':description,'tags':[t.strip('# ') for t in tags.split(',') if t.strip()],'categoryId':s.get('youtube.default_category_id','28')},'status':{'privacyStatus':s.get('youtube.privacy_status','private'),'selfDeclaredMadeForKids':s.get('youtube.made_for_kids',False)}}
    if publish_at: body['status']['publishAt']=publish_at; body['status']['privacyStatus']='private'
    yt=service(); res=yt.videos().insert(part='snippet,status', body=body, media_body=MediaFileUpload(video, chunksize=-1, resumable=True)).execute()
    if thumbnail and Path(thumbnail).exists(): yt.thumbnails().set(videoId=res['id'], media_body=MediaFileUpload(thumbnail)).execute()
    write_event('youtube_uploaded', {'video_id':res['id'],'video':video,'publish_at':publish_at}); return res['id']

def main(queue='output/scripts.json'):
    for idx,item in enumerate(json.loads(Path(queue).read_text(encoding='utf-8'))):
        jid=str(item['id']); upload(f'videos/{jid}.mp4', f'thumbnails/{jid}.jpg', item['title'], item['description'], ','.join(item.get('hashtags',[])), scheduled_time(idx))
if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--queue',default='output/scripts.json'); ap.add_argument('--video'); ap.add_argument('--thumbnail'); ap.add_argument('--title'); ap.add_argument('--description'); ap.add_argument('--tags',default=''); ap.add_argument('--publish-at')
    args=ap.parse_args(); upload(args.video,args.thumbnail,args.title,args.description,args.tags,args.publish_at) if args.video else main(args.queue)
