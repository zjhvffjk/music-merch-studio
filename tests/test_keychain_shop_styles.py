import os
import sys
import unittest
from pathlib import Path
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

    def test_shop_overview_keeps_the_selected_product_canvas_size(self):
        size = shop.canvas_size('square', 'square_ring')
        unit = Image.new('RGBA', size, (24, 72, 90, 255))
        overview = shop.build_grid([unit], bg='white', target_size=size)
        self.assertEqual(overview.size, size)
        self.assertEqual(overview.getpixel((0, 0)), (24, 72, 90, 255))
        overview.close()

        # 多首时仍输出同样的电商画布，只在画布内排版。
        multi = shop.build_grid([unit, unit], bg='white', target_size=size)
        self.assertEqual(multi.size, size)
        multi.close()
        unit.close()

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


if __name__ == '__main__':
    unittest.main()
