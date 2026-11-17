"""Authenticated web gateway and remote Streamable HTTP MCP for the existing studio."""
import asyncio
import base64
import hashlib
import hmac
import ipaddress
import os
import socket
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from urllib.parse import quote, urlencode, urlsplit

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import BaseModel, ConfigDict, Field
from starlette.applications import Starlette
from starlette.background import BackgroundTask
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response, StreamingResponse
from starlette.routing import Route

from .jobs import INTERNAL, OUTPUTS, Queue, api, files_under, identifier, project_dir, project_files

PUBLIC = os.environ.get('STUDIO_PUBLIC_URL', 'http://localhost:8080').rstrip('/')
USER = os.environ.get('STUDIO_WEB_USER', 'studio')
PASSWORD = os.environ.get('STUDIO_WEB_PASSWORD', '')
TOKEN = os.environ.get('STUDIO_MCP_TOKEN', '')
SIGNING = os.environ.get('STUDIO_DOWNLOAD_SECRET', '')
if min(len(PASSWORD), len(TOKEN), len(SIGNING)) < 24:
    raise RuntimeError('Set dedicated web password, MCP token and download secret (24+ characters each)')

queue = Queue(OUTPUTS / 'MCP' / 'tasks.sqlite3')
public_host = urlsplit(PUBLIC).netloc
mcp = FastMCP('Music Merch Studio', instructions='Search music, create mini-CD print materials and eight-view product images, and generate existing keychain/player products. Generation tools return a persistent task ID; poll get_task until complete, then use get_downloads. Mini-CD individual images are 8192x8192 and the overview is 8192x4096. Files retain the detail available in the original artwork and shell photos.',
              stateless_http=True, json_response=True, streamable_http_path='/mcp',
              transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=True,
                allowed_hosts=[public_host, 'localhost:*', '127.0.0.1:*', 'testserver'],
                allowed_origins=[PUBLIC]))
mcp_app = mcp.streamable_http_app()


def file_path(path):
    if not path or '\\' in path or any(p in ('', '.', '..') or p.startswith('.') for p in path.split('/')):
        raise ValueError('Invalid file path')
    target = (OUTPUTS / path).resolve()
    if not target.is_relative_to(OUTPUTS.resolve()) or not target.is_file() or target.suffix.lower() not in {'.png', '.jpg', '.jpeg', '.webp', '.pdf', '.zip', '.json'}:
        raise ValueError('File not found')
    if any(p.startswith('_') for p in Path(path).parts):
        raise ValueError('Private file')
    return target


def signature(path, expires):
    return hmac.new(SIGNING.encode(), f'{path}|{expires}'.encode(), hashlib.sha256).hexdigest()


def signed_file(path):
    target = file_path(path)
    expires = int(time.time()) + 3600
    return {'path': path, 'bytes': target.stat().st_size, 'expires': expires,
            'url': PUBLIC + '/download/' + quote(path, safe='/') + '?' + urlencode({'expires': expires, 'signature': signature(path, expires)})}


def authenticated(headers, kind):
    value = headers.get('authorization', '')
    if kind == 'mcp':
        return hmac.compare_digest(value, 'Bearer ' + TOKEN)
    try:
        user, password = base64.b64decode(value.removeprefix('Basic '), validate=True).decode().split(':', 1)
        return value.startswith('Basic ') and hmac.compare_digest(user, USER) and hmac.compare_digest(password, PASSWORD)
    except (ValueError, UnicodeError):
        return False


def valid_download(request):
    try:
        path = request.path_params['path']
        expires = int(request.query_params.get('expires', '0'))
        return time.time() < expires <= time.time() + 3660 and hmac.compare_digest(request.query_params.get('signature', ''), signature(path, expires))
    except (KeyError, ValueError):
        return False


class Authentication:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        request = Request(scope, receive)
        path = scope['path']
        if path == '/healthz':
            return await self.app(scope, receive, send)
        kind = 'mcp' if path == '/mcp' or path.startswith('/mcp/') else 'web'
        # Signed downloads are checked in their route after path parameters are available.
        if not path.startswith('/download/') and not authenticated(request.headers, kind):
            response = JSONResponse({'error': 'Authentication required'}, status_code=401,
                                    headers={'WWW-Authenticate': 'Bearer' if kind == 'mcp' else 'Basic realm="Music Studio", charset="UTF-8"'})
            return await response(scope, receive, send)
        if kind == 'web' and request.method not in ('GET', 'HEAD', 'OPTIONS'):
            origin = request.headers.get('origin')
            if origin and origin != PUBLIC:
                return await JSONResponse({'error': 'Origin not allowed'}, status_code=403)(scope, receive, send)
        return await self.app(scope, receive, send)


async def health(request):
    try:
        response = await request.app.state.client.get(INTERNAL + '/api/ping', timeout=5)
        return JSONResponse({'status': 'ok' if response.is_success else 'unavailable'}, status_code=200 if response.is_success else 503)
    except httpx.HTTPError:
        return JSONResponse({'status': 'unavailable'}, status_code=503)


async def download(request):
    if not (valid_download(request) or authenticated(request.headers, 'mcp') or authenticated(request.headers, 'web')):
        return JSONResponse({'error': 'Download link expired or invalid'}, status_code=401)
    try:
        target = file_path(request.path_params['path'])
    except ValueError:
        return JSONResponse({'error': 'File not found'}, status_code=404)
    return FileResponse(target, filename=target.name, headers={'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer'})


async def proxy(request):
    # Desktop-only file reveal is meaningless on a remote host.
    if request.url.path == '/api/reveal':
        return JSONResponse({'error': 'Use downloads on the remote workbench'}, status_code=400)
    length = request.headers.get('content-length')
    if length and (not length.isdecimal() or int(length) > 50 * 1024 * 1024):
        return JSONResponse({'error': 'Request too large'}, status_code=413)
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 50 * 1024 * 1024:
            return JSONResponse({'error': 'Request too large'}, status_code=413)
    path = request.url.path
    if request.url.query:
        path += '?' + request.url.query
    headers = {k: v for k, v in request.headers.items() if k.lower() in ('content-type', 'range', 'accept', 'if-none-match', 'if-modified-since')}
    client = request.app.state.client
    try:
        upstream = await client.send(client.build_request(request.method, INTERNAL + path, headers=headers, content=bytes(body)), stream=True)
    except httpx.HTTPError:
        return JSONResponse({'error': 'Workbench unavailable'}, status_code=502)
    response_headers = {k: v for k, v in upstream.headers.items() if k.lower() not in ('connection', 'transfer-encoding', 'keep-alive')}
    response_headers.update({'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'same-origin'})
    return StreamingResponse(upstream.aiter_raw(), status_code=upstream.status_code, headers=response_headers, background=BackgroundTask(upstream.aclose))


class Track(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=1, max_length=250)
    duration: str = Field(default='', max_length=20)


class Album(BaseModel):
    model_config = ConfigDict(extra='forbid')
    artist: str = Field(min_length=1, max_length=200)
    album: str = Field(min_length=1, max_length=200)
    cover_upload: str = Field(description='Upload ID from upload_image; no local filesystem paths')
    company: str = Field(default='', max_length=250)
    date: str = Field(default='', max_length=30)
    tracks: list[Track] = Field(default_factory=list, max_length=100)
    innerCopy: str = Field(default='', max_length=2000)
    copyright: str = Field(default='', max_length=2000)
    barcode: str = Field(default='', max_length=30)
    mood: str = Field(default='', max_length=100)
    style: str = Field(default='', max_length=100)


def album_payload(album):
    uid = identifier(album.cover_upload)
    uploads = OUTPUTS / '工作台' / '_uploads'
    candidates = [p for p in uploads.glob(uid + '.*') if p.is_file() and not p.is_symlink() and p.resolve().is_relative_to(uploads.resolve())]
    if not candidates:
        raise ValueError('Cover upload not found; call upload_image first')
    data = album.model_dump(exclude={'cover_upload'})
    data['pic'] = str(candidates[0])
    data['trackData'] = data.pop('tracks')
    return data


def public_url(url):
    parsed = urlsplit(url)
    if parsed.scheme not in ('http', 'https') or parsed.username or parsed.password or not parsed.hostname or parsed.port not in (None, 80, 443):
        raise ValueError('Use a public HTTP(S) image URL')
    addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == 'https' else 80), type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
        raise ValueError('Private network addresses are not accepted')
    return url


def fetch_image(url):
    with httpx.Client(timeout=45, trust_env=False) as client:
        for _ in range(5):
            public_url(url)
            with client.stream('GET', url) as response:
                if response.is_redirect:
                    from urllib.parse import urljoin
                    url = urljoin(url, response.headers['location'])
                    continue
                response.raise_for_status()
                data = bytearray()
                for chunk in response.iter_bytes(65536):
                    data.extend(chunk)
                    if len(data) > 20 * 1024 * 1024:
                        raise ValueError('Image exceeds 20 MB')
                return bytes(data)
    raise ValueError('Too many redirects')


@mcp.tool()
async def studio_status() -> dict:
    """Check connectivity, available production features and output dimensions."""
    return {'workbench': await asyncio.to_thread(api, 'GET', '/api/ping'), 'individual_pixels': [8192, 8192], 'overview_pixels': [8192, 4096], 'max_batch': 12, 'queue_limit': 20}


@mcp.tool()
async def search_music(query: str) -> dict:
    """Search songs, artists and albums by a name (1-200 characters)."""
    if not 1 <= len(query.strip()) <= 200:
        raise ValueError('Query must have 1-200 characters')
    return await asyncio.to_thread(api, 'GET', '/api/search', params={'name': query})


@mcp.tool()
async def artist_albums(artist: str, limit: int = 20) -> dict:
    """Read an artist's albums before choosing which ones to generate."""
    if not 1 <= len(artist.strip()) <= 200 or not 1 <= limit <= 100:
        raise ValueError('Invalid artist or limit')
    return await asyncio.to_thread(api, 'GET', '/api/albums', params={'name': artist, 'limit': limit})


@mcp.tool()
async def album_tracks(album_id: str) -> dict:
    """Get real album information and tracks using the music service album ID."""
    if not album_id.isdecimal() or len(album_id) > 20:
        raise ValueError('Album ID must be numeric')
    return await asyncio.to_thread(api, 'GET', '/api/album_songs', params={'id': album_id})


@mcp.tool()
async def list_projects() -> dict:
    """List saved mini-CD and original merchandise projects."""
    return await asyncio.to_thread(api, 'GET', '/api/jobs')


@mcp.tool()
async def get_project(project_id: str) -> dict:
    """Read a mini-CD project's metadata and list its generated files."""
    jid = identifier(project_id)
    return {'metadata': await asyncio.to_thread(api, 'GET', '/api/design/state', params={'jid': jid}), 'files': project_files(jid)}


@mcp.tool()
async def upload_image(name: str, image_url: str = '', base64_data: str = '') -> dict:
    """Upload PNG/JPEG/WebP artwork up to 20 MB. Supply one public image URL or base64 data, then use the returned upload ID as cover_upload."""
    if bool(image_url) == bool(base64_data):
        raise ValueError('Supply exactly one image_url or base64_data')
    if Path(name).suffix.lower() not in ('.png', '.jpg', '.jpeg', '.webp') or len(name) > 200:
        raise ValueError('Use a PNG/JPEG/WebP filename')
    if len(base64_data) > 28 * 1024 * 1024:
        raise ValueError('Image exceeds 20 MB')
    data = await asyncio.to_thread(fetch_image, image_url) if image_url else base64.b64decode(base64_data, validate=True)
    if not data or len(data) > 20 * 1024 * 1024:
        raise ValueError('Image must be 1 byte to 20 MB')
    return await asyncio.to_thread(api, 'POST', '/api/upload?' + urlencode({'name': Path(name).name}), content=data, headers={'Content-Type': 'application/octet-stream'})


@mcp.tool()
async def create_minicd(albums: list[Album], include_mockups: bool = True) -> dict:
    """Create print materials for 1-12 selected albums and optionally all eight 8K views plus overview. Returns a task ID; poll get_task. Each album needs a cover upload and real track data."""
    if not 1 <= len(albums) <= 12:
        raise ValueError('Provide 1-12 albums')
    return queue.submit('minicd', {'albums': [album_payload(album) for album in albums], 'mockups': include_mockups})


@mcp.tool()
async def generate_mockups(project_id: str) -> dict:
    """Generate one overview and eight independent 8K product images for an existing mini-CD project. Returns a task ID."""
    project_dir(project_id)
    return queue.submit('mockups', {'jid': project_id})


@mcp.tool()
async def create_merchandise(artist: str, song: str = '', mode: Literal['artist', 'song', 'album'] = 'artist', count: int = 10,
                             keychain: bool = True, shop_images: bool = True, vinyl: bool = False, album_cards: bool = True) -> dict:
    """Generate existing player/keychain/product-shot/vinyl/album-card products by artist or song. Returns a task ID; poll get_task for file results."""
    if not 1 <= len(artist.strip()) <= 200 or len(song) > 250 or not 1 <= count <= 50:
        raise ValueError('Invalid artist, song or count')
    if mode == 'song' and not song.strip():
        raise ValueError('Song name required')
    return queue.submit('merch', {'mode': mode, 'artist': artist, 'song': song, 'top': count, 'albumMax': count,
                                  'keychain': keychain, 'shop': shop_images, 'vinyl': vinyl, 'albumCard': album_cards})


@mcp.tool()
async def get_task(task_id: str) -> dict:
    """Read persistent task status, progress, errors and completed output file paths. Poll every 5-10 seconds until complete/failed/interrupted."""
    return queue.get(task_id)


@mcp.tool()
async def get_downloads(project_id: str = '', task_id: str = '') -> dict:
    """Return expiring download URLs for a project or completed task. Links last one hour; call again to refresh. No access token is placed in the URL."""
    if bool(project_id) == bool(task_id):
        raise ValueError('Supply exactly one project_id or task_id')
    if project_id:
        jid = identifier(project_id)
        try:
            files = project_files(jid)
        except ValueError:
            root = OUTPUTS / '工作台' / jid
            if not (root / 'meta.json').is_file():
                raise ValueError('Project not found')
            files = files_under(root)
    else:
        task = queue.get(task_id)
        if task['status'] != 'complete':
            return {'status': task['status'], 'progress': task['progress'], 'error': task['error']}
        result = task['result']
        files = list(result.get('files', []))
        for project in result.get('projects', []):
            files.extend(project['files'])
        if result.get('bundle'):
            files.append({'path': result['bundle']})
    return {'files': [signed_file(file['path']) for file in files]}


@asynccontextmanager
async def lifespan(app):
    async with httpx.AsyncClient(timeout=httpx.Timeout(900, connect=10), trust_env=False) as client:
        app.state.client = client
        queue.start()
        try:
            async with mcp.session_manager.run():
                yield
        finally:
            queue.stop()


app = Starlette(routes=[Route('/healthz', health), Route('/download/{path:path}', download),
                        Route('/mcp', mcp_app, methods=['GET', 'POST', 'DELETE']),
                        Route('/{path:path}', proxy, methods=['GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'])], lifespan=lifespan)
app.add_middleware(Authentication)
