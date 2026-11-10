"""Minimal authenticated HTTP entrypoint for Make.com to trigger the media pipeline.
The YouTube account is never accessed until its owner authorizes OAuth.
"""
import hmac
import os
import secrets
import subprocess
import sys
import threading
import time
from html import escape
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

app = FastAPI(title='Horror YouTube automation')
lock = threading.Lock()
state_lock = threading.Lock()
job = {'status': 'idle', 'message': 'Ready for a manual dry run', 'last_finished': None}
oauth_states = {}
ROOT = Path(__file__).parent
EXPECTED_CHANNEL = 'UC7DQ1Bd-smHjVQxAtN-1eTg'

class RunRequest(BaseModel):
    mode: Literal['short', 'long', 'both'] = 'both'
    publish: bool = False
    dry_mock: bool = False


def authenticate(actual: str):
    expected = os.environ.get('AUTOMATION_KEY', '')
    if len(expected) < 20 or not hmac.compare_digest(expected, actual or ''):
        raise HTTPException(status_code=401, detail='Invalid automation key')


@app.get('/health')
def health():
    return {'ok': True, 'service': 'horror-youtube-automation', 'publishing_enabled': os.getenv('ENABLE_AUTOPUBLISH', '').lower() == 'true'}


@app.get('/status')
def status(x_automation_key: str = Header(default='')):
    authenticate(x_automation_key)
    return job.copy()


def _runner(mode: str, publish: bool, mock: bool):
    command = [sys.executable, '-m', 'src.main', '--mode', mode]
    if publish:
        command.append('--upload')
    if mock:
        command.append('--mock')
    try:
        result = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=3 * 3600)
        with state_lock:
            if result.returncode:
                job.update({'status': 'failed', 'message': result.stdout[-1500:], 'last_finished': int(time.time())})
            else:
                job.update({'status': 'finished', 'message': result.stdout[-700:], 'last_finished': int(time.time())})
        print(result.stdout[-3000:], flush=True)
    except Exception as exc:
        with state_lock:
            job.update({'status': 'failed', 'message': str(exc)[:350], 'last_finished': int(time.time())})
    finally:
        lock.release()


@app.post('/run', status_code=202)
def run(payload: RunRequest, x_automation_key: str = Header(default='')):
    authenticate(x_automation_key)
    if payload.publish and payload.dry_mock:
        raise HTTPException(status_code=400, detail='Mock content must never be published')
    if payload.publish and os.getenv('ENABLE_AUTOPUBLISH', '').lower() != 'true':
        raise HTTPException(status_code=412, detail='Enable publishing in Render environment after dry run')
    if payload.publish and not all(os.getenv(k) for k in ('YOUTUBE_CLIENT_ID', 'YOUTUBE_CLIENT_SECRET', 'YOUTUBE_REFRESH_TOKEN')):
        raise HTTPException(status_code=412, detail='YouTube connection is not completed')
    if not payload.dry_mock and not os.getenv('GEMINI_API_KEY'):
        raise HTTPException(status_code=412, detail='Gemini API key is not configured')
    if not lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail='A render job is already running')
    job.update({'status': 'running', 'message': f'{payload.mode}, publish={payload.publish}', 'last_finished': None})
    threading.Thread(target=_runner, args=(payload.mode, payload.publish, payload.dry_mock), daemon=True).start()
    return {'ok': True, 'started': payload.mode, 'publish': payload.publish,
            'warning': 'Render Free may stop/restart a long job. Check /status with the secret header.'}


@app.get('/connect', response_class=HTMLResponse)
def connect_form():
    return HTMLResponse('<!doctype html><html lang="ar" dir="rtl"><meta charset="utf-8">'
                        '<title>ربط قناة يوتيوب</title><body style="font:18px system-ui;max-width:600px;margin:50px auto">'
                        '<h2>ربط قناة الرعب مرة واحدة</h2><p>أدخل مفتاح الإدارة من إعدادات Render. لا ترسله في أي محادثة.</p>'
                        '<form method="post" action="/connect"><input name="secret" type="password" required '
                        'style="padding:12px;width:70%"><button style="padding:12px">ربط Google</button></form></body></html>')


@app.post('/connect')
async def connect(request: Request):
    form = await request.form()
    authenticate(str(form.get('secret', '')))
    client_id, client_secret = os.getenv('YOUTUBE_CLIENT_ID'), os.getenv('YOUTUBE_CLIENT_SECRET')
    if not client_id or not client_secret:
        raise HTTPException(status_code=412, detail='Set YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET in Render first')
    from google_auth_oauthlib.flow import Flow
    scopes = ['https://www.googleapis.com/auth/youtube.upload', 'https://www.googleapis.com/auth/youtube.readonly']
    redirect_uri = str(request.url_for('oauth_callback')).replace('http://', 'https://')
    conf = {'web': {'client_id': client_id, 'client_secret': client_secret,
                    'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                    'token_uri': 'https://oauth2.googleapis.com/token',
                    'redirect_uris': [redirect_uri]}}
    flow = Flow.from_client_config(conf, scopes=scopes, redirect_uri=redirect_uri)
    auth_url, state = flow.authorization_url(access_type='offline', prompt='consent')
    oauth_states[state] = {'conf': conf, 'scopes': scopes, 'redirect_uri': redirect_uri, 'created': time.time()}
    return RedirectResponse(auth_url, status_code=303)


@app.get('/oauth/callback', name='oauth_callback')
def oauth_callback(request: Request, state: str = ''):
    item = oauth_states.pop(state, None)
    if not item or time.time() - item['created'] > 600:
        raise HTTPException(status_code=400, detail='OAuth state missing or expired. Restart from /connect')
    from google_auth_oauthlib.flow import Flow
    from googleapiclient.discovery import build
    flow = Flow.from_client_config(item['conf'], scopes=item['scopes'], state=state, redirect_uri=item['redirect_uri'])
    response_url = str(request.url).replace('http://', 'https://')
    flow.fetch_token(authorization_response=response_url)
    creds = flow.credentials
    if not creds.refresh_token:
        raise HTTPException(status_code=400, detail='No refresh token received. Revoke prior access and try again.')
    yt = build('youtube', 'v3', credentials=creds, cache_discovery=False)
    channels = yt.channels().list(part='id,snippet', mine=True).execute().get('items', [])
    if not channels or channels[0]['id'] != EXPECTED_CHANNEL:
        raise HTTPException(status_code=403, detail='Wrong channel selected. No permissions stored, no upload attempted.')
    token = escape(creds.refresh_token)
    return HTMLResponse('<!doctype html><html lang="ar" dir="rtl"><meta charset="utf-8">'
                        '<body style="font:18px system-ui;max-width:800px;margin:40px auto">'
                        '<h2>تم التأكد من القناة الصحيحة</h2><p>انسخ الرمز التالي في Render Environment فقط '
                        'باسم <code>YOUTUBE_REFRESH_TOKEN</code>، ولا تنشره أو ترسله في الشات.</p>'
                        '<textarea readonly style="width:100%;height:130px">'+token+'</textarea>'
                        '<p>سيختفي هذا الرمز عند غلق الصفحة، ولا يتم تخزينه داخل التطبيق.</p></body></html>',
                        headers={'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer'})
