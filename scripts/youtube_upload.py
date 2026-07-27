from __future__ import annotations
import argparse, datetime as dt
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
    creds=Credentials.from_authorized_user_file(token, SCOPES) if token.exists() else None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token: creds.refresh(Request())
        else: creds=InstalledAppFlow.from_client_secrets_file(secret, SCOPES).run_local_server(port=0)
        token.parent.mkdir(exist_ok=True); token.write_text(creds.to_json(), encoding='utf-8')
    return build('youtube','v3',credentials=creds)

def upload(video, thumbnail, title, description, tags='', publish_at=None):
    s=load_settings(); body={'snippet':{'title':title,'description':description,'tags':[t.strip() for t in tags.split(',') if t.strip()],'categoryId':s.get('youtube.default_category_id','28')},'status':{'privacyStatus':s.get('youtube.privacy_status','private'),'selfDeclaredMadeForKids':s.get('youtube.made_for_kids',False)}}
    if publish_at: body['status']['publishAt']=publish_at; body['status']['privacyStatus']='private'
    yt=service(); res=yt.videos().insert(part='snippet,status', body=body, media_body=MediaFileUpload(video, chunksize=-1, resumable=True)).execute()
    if thumbnail: yt.thumbnails().set(videoId=res['id'], media_body=MediaFileUpload(thumbnail)).execute()
    write_event('youtube_uploaded', {'video_id':res['id'],'video':video}); return res['id']
if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--video',required=True); ap.add_argument('--thumbnail'); ap.add_argument('--title',required=True); ap.add_argument('--description',required=True); ap.add_argument('--tags',default=''); ap.add_argument('--publish-at'); print(upload(**vars(ap.parse_args())))
