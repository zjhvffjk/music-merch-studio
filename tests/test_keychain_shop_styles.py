import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import make_keychain_shop as shop


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


if __name__ == '__main__':
    unittest.main()
