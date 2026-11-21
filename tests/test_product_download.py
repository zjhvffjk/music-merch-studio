import http.client
import io
import json
import sys
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from urllib.parse import quote
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "workbench"))
import server  # noqa: E402


class ProductDownloadTests(unittest.TestCase):
    def test_product_download_returns_complete_zip_as_attachment(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as archive:
            archive.writestr("原有素材和打印文件/打印拼版-A4.pdf", b"p" * (1024 * 1024 + 7))
            archive.writestr("九视图商品图/封面.jpg", b"jpeg")
        payload = data.getvalue()
        filename = quote("专辑-素材和商品图.zip")
        with (tempfile.TemporaryDirectory() as folder,
              patch.object(server, "OUT_ROOT", folder),
              server.Server(("127.0.0.1", 0), server.Handler) as httpd):
            worker = threading.Thread(target=httpd.serve_forever, daemon=True)
            worker.start()
            conn = http.client.HTTPConnection("127.0.0.1", httpd.server_port, timeout=5)
            try:
                conn.request("POST", "/api/product-download?name=" + filename, payload, {
                    "Origin": f"http://127.0.0.1:{httpd.server_port}",
                    "Content-Type": "application/zip",
                })
                result = conn.getresponse()
                self.assertEqual(result.status, 200)
                url = json.loads(result.read())["url"]
                conn.request("GET", url)
                response = conn.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(response.getheader("Content-Type"), "application/zip")
                self.assertEqual(response.getheader("Content-Disposition"),
                                 "attachment; filename*=UTF-8''" + filename)
                self.assertEqual(response.read(), payload)
            finally:
                conn.close()
                httpd.shutdown()
                worker.join()
