"""Persistent, bounded, serial production queue and the existing browser renderer."""
import asyncio
import json
import os
import re
import sqlite3
import threading
import time
import uuid
import zipfile
from pathlib import Path
from contextlib import contextmanager
from urllib.parse import urlencode

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = ROOT / 'outputs'
INTERNAL = os.environ.get('STUDIO_INTERNAL_URL', 'http://127.0.0.1:8765').rstrip('/')


def identifier(value):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', str(value)):
        raise ValueError('Invalid project or task ID')
    return str(value)


def project_dir(jid):
    path = OUTPUTS / '迷你CD设计' / identifier(jid)
    if not (path / 'meta.json').is_file():
        raise ValueError('Project not found')
    return path


def api(method, path, **kwargs):
    with httpx.Client(timeout=900, trust_env=False) as client:
        response = client.request(method, INTERNAL + path, **kwargs)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict) and data.get('error'):
            raise ValueError(str(data['error'])[:500])
        return data


class Queue:
    def __init__(self, database):
        self.database = Path(database)
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self.signal = threading.Event()
        self.stopping = threading.Event()
        self.thread = None
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, kind TEXT, status TEXT, progress TEXT, payload TEXT, result TEXT, error TEXT, created REAL, updated REAL)')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.database, timeout=20)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def start(self):
        with self.connect() as db:
            db.execute("UPDATE tasks SET status='interrupted',error='Service restarted; completed files are preserved. Submit a new task to retry.',updated=? WHERE status='running'", (time.time(),))
        self.thread = threading.Thread(target=self.run, daemon=True, name='studio-production')
        self.thread.start()

    def stop(self):
        self.stopping.set()
        self.signal.set()

    def submit(self, kind, payload):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute("SELECT count(*) FROM tasks WHERE status IN ('queued','running')").fetchone()[0] >= 20:
                raise ValueError('Queue full; wait for existing tasks to finish')
            task_id = uuid.uuid4().hex
            now = time.time()
            db.execute('INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?)', (task_id, kind, 'queued', '等待生成', json.dumps(payload, ensure_ascii=False), None, None, now, now))
        self.signal.set()
        return self.get(task_id)

    def get(self, task_id):
        with self.connect() as db:
            row = db.execute('SELECT * FROM tasks WHERE id=?', (identifier(task_id),)).fetchone()
        if not row:
            raise ValueError('Task not found')
        return {key: json.loads(row[key]) if key == 'result' and row[key] else row[key] for key in row.keys() if key != 'payload'}

    def progress(self, task_id, message):
        with self.connect() as db:
            db.execute('UPDATE tasks SET progress=?,updated=? WHERE id=?', (str(message)[:300], time.time(), task_id))

    def run(self):
        while not self.stopping.is_set():
            with self.connect() as db:
                row = db.execute("SELECT * FROM tasks WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
                if row:
                    db.execute("UPDATE tasks SET status='running',updated=? WHERE id=?", (time.time(), row['id']))
            if not row:
                self.signal.wait(2)
                self.signal.clear()
                continue
            try:
                result = self.execute(row['id'], row['kind'], json.loads(row['payload']))
                with self.connect() as db:
                    db.execute("UPDATE tasks SET status='complete',progress='已完成',result=?,updated=? WHERE id=?", (json.dumps(result, ensure_ascii=False), time.time(), row['id']))
            except Exception as exc:
                with self.connect() as db:
                    db.execute("UPDATE tasks SET status='failed',error=?,updated=? WHERE id=?", (str(exc)[:1000], time.time(), row['id']))

    def execute(self, task_id, kind, payload):
        progress = lambda text: self.progress(task_id, text)
        if kind == 'mockups':
            jid = identifier(payload['jid'])
            asyncio.run(render_mockups(jid, progress))
            return {'jid': jid, 'files': project_files(jid)}
        if kind == 'merch':
            progress('原有商品图生成中')
            state = api('POST', '/api/run', json=payload)
            deadline = time.monotonic() + 3600
            while state['status'] not in ('done', 'error'):
                if time.monotonic() > deadline or self.stopping.wait(2):
                    raise RuntimeError('Generation interrupted or timed out; check the workbench project before retrying')
                progress(state.get('phase') or '生成中')
                state = api('GET', '/api/state', params={'id': state['id']})
            if state['status'] == 'error':
                raise RuntimeError(state.get('error') or 'Generation failed')
            root = OUTPUTS / '工作台' / identifier(state['id'])
            return {'jid': state['id'], 'files': files_under(root)}
        if kind != 'minicd':
            raise ValueError('Unsupported task kind')
        results = []
        for number, album in enumerate(payload['albums'], 1):
            progress(f"生成三件套 {number}/{len(payload['albums'])}：{album.get('album', '')}")
            result = api('POST', '/api/design/build', json={**album, 'id': 'mcp-' + uuid.uuid4().hex[:16]})
            jid = identifier(result['jid'])
            if payload.get('mockups', True):
                asyncio.run(render_mockups(jid, progress))
            results.append({'jid': jid, 'album': album['album'], 'files': project_files(jid)})
        if len(results) > 1:
            bundle = OUTPUTS / 'MCP' / (task_id + '.zip')
            bundle.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(bundle, 'w', zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
                for number, result in enumerate(results, 1):
                    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', '_', result['album'])[:70]
                    base = project_dir(result['jid'])
                    for file in project_files(result['jid']):
                        archive.write(OUTPUTS / file['path'], f'{number:02d}-{name}/{file["name"]}')
            return {'projects': results, 'bundle': bundle.relative_to(OUTPUTS).as_posix()}
        return {'projects': results}


def project_files(jid):
    root = project_dir(jid)
    files = files_under(root)
    bundle = root.with_suffix('.zip')
    if bundle.is_file():
        files.append({'name': '原有素材.zip', 'bytes': bundle.stat().st_size, 'path': bundle.relative_to(OUTPUTS).as_posix()})
    return files


def files_under(root):
    allowed = {'.png', '.jpg', '.jpeg', '.pdf', '.zip', '.json'}
    return [{'name': p.relative_to(root).as_posix(), 'bytes': p.stat().st_size,
             'path': p.relative_to(OUTPUTS).as_posix()} for p in sorted(root.rglob('*'))
            if p.is_file() and not p.is_symlink() and p.resolve().is_relative_to(root.resolve())
            and p.suffix.lower() in allowed and not p.name.startswith('.')]


async def render_mockups(jid, progress):
    """Render one image at a time using the same modules as the workbench."""
    from playwright.async_api import async_playwright

    directory = project_dir(jid)
    destination = directory / '商品图'
    destination.mkdir(exist_ok=True)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, args=['--disable-dev-shm-usage'])
        try:
            page = await browser.new_page(viewport={'width': 1400, 'height': 1000})
            # A same-origin empty harness avoids starting the interactive app and its background rendering.
            await page.route('**/__mcp-render?*', lambda route: route.fulfill(content_type='text/html', body='<!doctype html><html><body></body></html>'))
            await page.goto(INTERNAL + '/__mcp-render?' + urlencode({'jid': jid}), wait_until='domcontentloaded', timeout=90000)
            await page.evaluate('''async () => {
              const model = await import('/mini-mockup/model.js');
              const renderer = await import('/mini-mockup/renderer.js');
              const state = model.initialState();
              state.showDesign = true; state.discVisible = true;
              const names = {front:'封面',back:'封底',inside:'封面背面',tray:'内盘底',disc:'盘面',sideR:'右侧封',sideL:'左侧封',sideLB:'左侧封背面'};
              const jid = new URLSearchParams(location.search).get('jid');
              for (const [slot, name] of Object.entries(names)) {
                const query = new URLSearchParams({jid, name:name+'.png'});
                if(slot==='back') {const response=await fetch('/api/design/highres-back?'+new URLSearchParams({jid})); if(response.ok){state.assets[slot].src=URL.createObjectURL(await response.blob());continue}}
                state.assets[slot].src = '/api/design/file?'+query;
              }
              await document.fonts.ready;
              await renderer.preloadShells();
              await renderer.prepareProjectAssets(state.assets);
              window.__mcpRender = {state, renderer, indices:model.views.map((v,i)=>v.hidden?-1:i).filter(i=>i>=0), names:model.views.map(v=>v.name)};
            }''')
            indices = await page.evaluate('window.__mcpRender.indices')
            for number, view in enumerate([-1, *indices]):
                label = '八视图总预览' if view == -1 else await page.evaluate('(i)=>window.__mcpRender.names[i]', view)
                progress(f'生成商品图 {number + 1}/9：{label}')
                import base64
                data = await page.evaluate('''async (view) => {
                  const {state,renderer}=window.__mcpRender;
                  const blob=await renderer.exportPNG({...state,view:view<0?0:view},8192,view<0?'sheet':'individual');
                  return await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.onerror=reject;reader.readAsDataURL(blob)});
                }''', view)
                (destination / f'{number:02d}-{label}.png').write_bytes(base64.b64decode(data))
                del data
        finally:
            await browser.close()
    bundle = directory / '素材和商品图.zip'
    source_bundle = directory.with_suffix('.zip')
    if not source_bundle.is_file():
        raise ValueError('Original material bundle is missing')
    with zipfile.ZipFile(source_bundle) as source, zipfile.ZipFile(bundle, 'w', zipfile.ZIP_DEFLATED, compresslevel=1) as out:
        for entry in source.infolist():
            if not entry.is_dir():
                with source.open(entry) as src, out.open('原有素材/' + entry.filename, 'w') as dst:
                    import shutil
                    shutil.copyfileobj(src, dst, 1024 * 1024)
        for image in sorted(destination.glob('*.png')):
            out.write(image, '商品图/' + image.name)
