"""Verify the remote authentication boundary, MCP protocol and persistent queue."""
import base64
import json
import os
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.update(STUDIO_WEB_PASSWORD='test-web-' + 'a' * 24,
                  STUDIO_MCP_TOKEN='test-agent-' + 'b' * 24,
                  STUDIO_DOWNLOAD_SECRET='test-sign-' + 'c' * 24)
from deploy import gateway as g
from deploy.jobs import Queue
from starlette.testclient import TestClient


class GatewayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context = TestClient(g.app)
        cls.client = cls.context.__enter__()
        cls.headers = {'Authorization': 'Bearer ' + g.TOKEN, 'Accept': 'application/json, text/event-stream'}

    @classmethod
    def tearDownClass(cls):
        cls.context.__exit__(None, None, None)

    def test_authentication_separated(self):
        for path in ('/', '/api/jobs', '/mcp'):
            self.assertEqual(self.client.get(path).status_code, 401)
        basic = 'Basic ' + base64.b64encode(f'{g.USER}:{g.PASSWORD}'.encode()).decode()
        self.assertEqual(self.client.get('/mcp', headers={'Authorization': basic}).status_code, 401)
        self.assertEqual(self.client.get('/', headers=self.headers).status_code, 401)

    def test_real_mcp_initialization_and_tools(self):
        response = self.client.post('/mcp', headers=self.headers, json={'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
          'params': {'protocolVersion': '2025-03-26', 'capabilities': {}, 'clientInfo': {'name': 'deployment-test', 'version': '1'}}})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn('serverInfo', response.json()['result'])
        response = self.client.post('/mcp', headers=self.headers, json={'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list', 'params': {}})
        self.assertEqual(response.status_code, 200, response.text)
        tools = {tool['name']: tool for tool in response.json()['result']['tools']}
        self.assertGreaterEqual(len(tools), 12)
        self.assertIn('create_minicd', tools)
        response = self.client.post('/mcp', headers=self.headers, json={'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call',
            'params': {'name': 'create_minicd', 'arguments': {'albums': []}}})
        self.assertTrue(response.json()['result']['isError'])

    def test_signed_files_and_traversal(self):
        path = 'MCP/test-' + uuid.uuid4().hex + '.png'
        target = g.OUTPUTS / path
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(b'file-boundary-test')
        try:
            link = g.signed_file(path)['url']
            url = link.removeprefix(g.PUBLIC)
            self.assertEqual(self.client.get(url).content, b'file-boundary-test')
            self.assertEqual(self.client.get(url + 'x').status_code, 401)
            self.assertEqual(self.client.get('/download/' + path).status_code, 401)
            for invalid in ('../requirements.txt', 'MCP/../../requirements.txt', 'MCP\\tasks.sqlite3', 'MCP/tasks.sqlite3', '_uploads/file.png'):
                with self.assertRaises(ValueError):
                    g.file_path(invalid)
        finally:
            target.unlink()

    def test_csrf(self):
        basic = 'Basic ' + base64.b64encode(f'{g.USER}:{g.PASSWORD}'.encode()).decode()
        response = self.client.post('/api/run', headers={'Authorization': basic, 'Origin': 'https://untrusted.example'}, json={})
        self.assertEqual(response.status_code, 403)


class QueueTest(unittest.TestCase):
    def test_persistence_limits_and_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'tasks.sqlite3'
            queue = Queue(path)
            ids = [queue.submit('minicd', {'albums': []})['id'] for _ in range(20)]
            with self.assertRaises(ValueError):
                queue.submit('minicd', {'albums': []})
            restored = Queue(path)
            self.assertEqual(restored.get(ids[0])['status'], 'queued')
            with restored.connect() as db:
                db.execute("UPDATE tasks SET status='running' WHERE id=?", (ids[0],))
                db.execute("UPDATE tasks SET status='complete' WHERE id!=?", (ids[0],))
            restored.start()
            try:
                self.assertEqual(restored.get(ids[0])['status'], 'interrupted')
            finally:
                restored.stop()
                restored.thread.join(timeout=5)


if __name__ == '__main__':
    unittest.main()
