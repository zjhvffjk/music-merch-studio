"""Check the production web entry and retired remote API boundary."""
import base64
import importlib
import os
import sys
import unittest
from pathlib import Path

import httpx
from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.update(STUDIO_WEB_USER='studio', STUDIO_WEB_PASSWORD='test-' + 'a' * 30,
                  STUDIO_PUBLIC_URL='https://music.haoquanwo.cloud')
web = importlib.import_module('deploy.web')


class WebDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.context = TestClient(web.app)
        self.client = self.context.__enter__()
        self.auth = {'Authorization': 'Basic ' + base64.b64encode(
            f'{web.USER}:{web.PASSWORD}'.encode()).decode()}

    def tearDown(self):
        self.context.__exit__(None, None, None)

    def test_login_required_and_remote_api_retired(self):
        self.assertEqual(self.client.get('/').status_code, 401)
        self.assertEqual(self.client.get('/api/jobs').status_code, 401)
        for path in ('/mcp', '/mcp/', '/download/old.png'):
            self.assertEqual(self.client.post(path, headers=self.auth).status_code, 404)

    def test_same_origin_and_browser_download_proxy(self):
        def upstream(request):
            if request.url.path == '/api/ping':
                return httpx.Response(200, json={'ok': True})
            return httpx.Response(200, stream=httpx.ByteStream(b'workbench-response'))
        previous = web.app.state.client
        web.app.state.client = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
        try:
            self.assertEqual(self.client.get('/healthz').status_code, 200)
            self.assertEqual(self.client.get('/design.html', headers=self.auth).content, b'workbench-response')
            self.assertEqual(self.client.get('/api/design/zip?jid=example', headers=self.auth).content,
                             b'workbench-response')
            self.assertEqual(self.client.post('/api/run', headers={**self.auth,
                             'Origin': 'https://other.example'}).status_code, 403)
            self.assertEqual(self.client.post('/api/reveal', headers=self.auth).status_code, 400)
        finally:
            web.app.state.client = previous
