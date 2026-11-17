"""Public web entry for the existing workbench application."""
import os
from contextlib import asynccontextmanager

import httpx
from starlette.applications import Starlette
from starlette.background import BackgroundTask
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Route

INTERNAL = 'http://127.0.0.1:8765'
PUBLIC = os.environ.get('STUDIO_PUBLIC_URL', 'http://localhost:8080').rstrip('/')


class PublicAccess:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        request = Request(scope, receive)
        path = scope['path']
        if path == '/healthz':
            return await self.app(scope, receive, send)
        # Retired remote API and signed links must never reach the workbench.
        if path == '/mcp' or path.startswith(('/mcp/', '/download/')):
            return await JSONResponse({'error': 'Not found'}, status_code=404)(scope, receive, send)
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            origin = request.headers.get('origin')
            if origin and origin != PUBLIC:
                return await JSONResponse({'error': 'Origin not allowed'}, status_code=403)(scope, receive, send)
        return await self.app(scope, receive, send)


async def health(request):
    try:
        response = await request.app.state.client.get(INTERNAL + '/api/ping', timeout=5)
        healthy = response.is_success
        return JSONResponse({'status': 'ok' if healthy else 'unavailable'}, status_code=200 if healthy else 503)
    except httpx.HTTPError:
        return JSONResponse({'status': 'unavailable'}, status_code=503)


async def proxy(request):
    if request.url.path == '/api/reveal':
        return JSONResponse({'error': 'Use browser downloads on the server'}, status_code=400)
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
    headers = {k: v for k, v in request.headers.items()
               if k.lower() in ('content-type', 'range', 'accept', 'if-none-match', 'if-modified-since')}
    client = request.app.state.client
    try:
        upstream = await client.send(client.build_request(request.method, INTERNAL + path,
                                     headers=headers, content=bytes(body)), stream=True)
    except httpx.HTTPError:
        return JSONResponse({'error': 'Workbench unavailable'}, status_code=502)
    response_headers = {k: v for k, v in upstream.headers.items()
                        if k.lower() not in ('connection', 'transfer-encoding', 'keep-alive')}
    response_headers.update({'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'same-origin'})
    return StreamingResponse(upstream.aiter_raw(), status_code=upstream.status_code,
                             headers=response_headers, background=BackgroundTask(upstream.aclose))


@asynccontextmanager
async def lifespan(app):
    async with httpx.AsyncClient(timeout=httpx.Timeout(900, connect=10), trust_env=False) as client:
        app.state.client = client
        yield


app = Starlette(routes=[Route('/healthz', health),
                        Route('/{path:path}', proxy, methods=['GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'])],
                lifespan=lifespan)
app.add_middleware(PublicAccess)
