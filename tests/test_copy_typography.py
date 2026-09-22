import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools")]


class CopyTypographyTests(unittest.TestCase):
    def test_explicit_layout_is_not_overridden(self):
        from copy_typography import normalize_copy_settings, recommend_copy_layout
        self.assertEqual(recommend_copy_layout(normalize_copy_settings({"copyLayout": "minimal"}), {"style": "bold"}), "minimal")

    def test_empty_copy_does_not_invent_reference_words(self):
        from copy_typography import normalize_copy_settings
        self.assertEqual(normalize_copy_settings({})["conceptCopy"], {"primaryChinese": "", "secondaryEnglish": "", "shortEnglish": ""})


if __name__ == "__main__":
    unittest.main()
