import io
import sys
import tempfile
import unittest
from http.client import IncompleteRead
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "workbench"), str(ROOT / "tools")]

import design_service


class CoverDownloadRecoveryTests(unittest.TestCase):
    def test_truncated_netease_cover_uses_same_image_at_supported_size(self):
        url = "https://p1.music.126.net/example==/109951171855825453.jpg"
        complete = io.BytesIO()
        Image.new("RGB", (1600, 1600), "#8b437d").save(complete, "JPEG")
        calls = []

        def open_cover(request, timeout):
            target = urlsplit(request.full_url)
            calls.append(target)
            if not target.query:
                raise IncompleteRead(b"partial response", 418340)
            return io.BytesIO(complete.getvalue())

        with tempfile.TemporaryDirectory() as directory, \
                patch.object(design_service, "OUT_DIR", Path(directory)), \
                patch("urllib.request.urlopen", side_effect=open_cover):
            cover = design_service._fetch_cover(url)

        self.assertIsNotNone(cover)
        self.assertEqual(cover.size, (1600, 1600))
        self.assertEqual([p.path for p in calls], [urlsplit(url).path] * 2)
        self.assertEqual(calls[1].query, "param=1600y1600")
        self.assertNotEqual(calls[0].hostname, calls[1].hostname)


if __name__ == "__main__":
    unittest.main()
