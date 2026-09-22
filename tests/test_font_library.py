import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools')]
import typo


class FontLibraryTests(unittest.TestCase):
    def test_selected_chinese_display_font_resolves_to_real_font_file(self):
        token = typo.set_font_overrides({'display': 'noto-serif-sc'})
        try:
            path = typo.resolved_font_path('serif', '如果呢')
        finally:
            typo.reset_font_overrides(token)
        self.assertTrue(path and Path(path).is_file())
        self.assertEqual('NotoSerifSC-VF.ttf', Path(path).name)

    def test_latin_font_is_not_used_for_chinese_text(self):
        token = typo.set_font_overrides({'display': 'georgia'})
        try:
            path = typo.resolved_font_path('serif', '如果呢')
        finally:
            typo.reset_font_overrides(token)
        self.assertNotEqual('georgia.ttf', Path(path).name.lower())


if __name__ == '__main__':
    unittest.main()
