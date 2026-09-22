import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools")]
from title_assets import save_title_asset

class TitleAssetTests(unittest.TestCase):
    def test_png_asset_preserves_alpha_and_records_visible_bounds(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "title.png"
            im = Image.new("RGBA", (200, 100), (0,0,0,0)); ImageDraw.Draw(im).rectangle((20,10,179,89), fill=(0,0,0,255)); im.save(path)
            asset = save_title_asset(path, "album-a")
            self.assertTrue(asset.transparent)
            self.assertEqual((20,10,180,90), asset.visible_bounds)

    def test_rejects_non_image_upload(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bad.txt"; path.write_text("bad")
            with self.assertRaisesRegex(ValueError, "PNG|SVG"):
                save_title_asset(path, "album-a")

if __name__ == "__main__": unittest.main()
