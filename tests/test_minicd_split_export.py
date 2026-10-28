"""Check that each uploaded mini CD component survives export."""

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "workbench"))
import design_service as service  # noqa: E402


class MiniCdSplitExportTest(unittest.TestCase):
    def test_both_spines_and_disc_sheet_are_exported(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cover = base / "cover.png"
            right = base / "right.png"
            left = base / "left.png"
            Image.new("RGB", (128, 128), "#e8d5ea").save(cover)
            Image.new("RGB", (24, 160), "#d02040").save(right)
            Image.new("RGB", (24, 160), "#2040d0").save(left)
            with patch.object(service, "OUT_DIR", base), patch.object(service, "DPI", 96), patch.object(service, "SHEET_DPI", 96):
                result = service.build_job({
                    "id": "test-minicd", "artist": "测试歌手", "album": "测试专辑",
                    "pic": str(cover), "date": "2026-01-01", "company": "测试厂牌",
                    "aiSideR": str(right), "aiSideL": str(left),
                })
            job = base / result["jid"]
            with Image.open(job / "右侧封.png") as image:
                self.assertEqual(image.getpixel((image.width // 2, image.height // 2)), (208, 32, 64))
            with Image.open(job / "左侧封.png") as image:
                self.assertEqual(image.getpixel((image.width // 2, image.height // 2)), (32, 64, 208))
            with zipfile.ZipFile(base / "test-minicd.zip") as bundle:
                names = set(bundle.namelist())
            self.assertTrue({"右侧封.png", "左侧封.png", "盘面拼版-A4.png", "盘面拼版-A4.pdf"} <= names)
            self.assertEqual(len(result["splitFiles"]), 8)


if __name__ == "__main__":
    unittest.main()
