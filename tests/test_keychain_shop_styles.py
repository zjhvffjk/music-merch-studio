import os
import sys
import unittest
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'workbench'))
import make_keychain_shop as shop
import make_keychain as scene
import server


class SquareRingKeychainTests(unittest.TestCase):
    def test_square_ring_style_is_a_real_composite_with_its_own_window(self):
        self.assertIn('square_ring', shop.STYLE_SPEC)
        spec = shop.style_info('square_ring')
        self.assertTrue(os.path.isfile(spec['path']))
        overlay = shop.load_overlay_trimmed('square_ring')
        self.assertEqual(overlay.size, (1153, 1207))
        player = ROOT / 'assets' / 'keychain' / 'player_1152x1920.jpg'
        result = shop.build_unit(str(player), overlay, kind='square', bg='transparent',
                                 style='square_ring')
        self.assertEqual(result.size, (1920, 1920))
        self.assertIsNotNone(result.getchannel('A').getbbox())
        overlay.close()
        result.close()

    def test_unknown_style_falls_back_to_existing_classic_style(self):
        self.assertEqual(shop.parse_style('not-a-style'), 'classic')

    def test_square_ring_style_is_available_to_the_scene_product_image_too(self):
        self.assertIn('square_ring', scene.STYLE_SPEC)
        overlay, lut = scene.prepare(style='square_ring')
        self.assertEqual(overlay.size, (scene.CANVAS, scene.CANVAS))
        self.assertEqual(scene.style_info('square_ring')['player'], (734, 866, 452, 687))
        overlay.close()

    def test_both_styles_are_kept_when_one_run_requests_them_together(self):
        self.assertEqual(
            server.keychain_styles({'keychainStyles': ['classic', 'square_ring']}),
            ['classic', 'square_ring'])
        self.assertEqual(
            server.shop_styles_selected({'shopStyles': ['classic', 'square_ring']}),
            ['classic', 'square_ring'])

    def test_product_zip_preserves_print_bytes_and_does_not_upscale(self):
        with TemporaryDirectory() as folder:
            job = Path(folder)
            (job / 'keychain').mkdir()
            (job / 'print').mkdir()
            sample = Image.new('RGBA', (24, 16), (200, 40, 60, 0))
            sample.putpixel((4, 4), (30, 120, 80, 128))
            sample.save(job / 'keychain' / 'product.png')
            sample.save(job / 'print' / 'layout.png', dpi=(600, 600))
            original = (job / 'print' / 'layout.png').read_bytes()
            (job / 'print' / 'layout.pdf').write_bytes(b'%PDF-1.4\n')

            archive = server.build_zip(job, '样张', 'product-4k')
            with ZipFile(archive) as result:
                self.assertEqual(result.read('打印文件/layout.png'), original)
                self.assertEqual(result.read('打印文件/layout.pdf'), b'%PDF-1.4\n')
                product = result.read('钥匙扣商品图/product.jpg')
            with Image.open(BytesIO(product)) as image:
                self.assertEqual(image.size, sample.size)
                self.assertEqual(image.format, 'JPEG')


if __name__ == '__main__':
    unittest.main()
