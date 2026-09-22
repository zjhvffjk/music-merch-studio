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

    def test_editorial_tagline_splits_into_a_compact_two_line_block(self):
        from PIL import Image, ImageDraw
        from design_parts import editorial_tag_lines
        lines = editorial_tag_lines(ImageDraw.Draw(Image.new("RGB", (400, 120))),
                                    "KEEP MOVING WITH THE LIGHT.", 260, 18)
        self.assertEqual(lines, ["KEEP MOVING", "WITH THE LIGHT."])

    def test_minimal_disc_tagline_uses_a_narrow_multiline_block(self):
        from PIL import Image, ImageDraw
        from design_parts import disc_tag_lines
        lines = disc_tag_lines(ImageDraw.Draw(Image.new("RGB", (400, 120))),
                               "MUSIC CONNECTS A BRIGHTER TOMORROW.", "minimal", 80, 15)
        self.assertEqual(len(lines), 4)
        self.assertEqual("MUSIC CONNECTS A BRIGHTER TOMORROW.", " ".join(lines))

    def test_copy_is_not_tilted_by_default(self):
        from design_parts import _copy_angle
        from copy_typography import normalize_copy_settings
        self.assertEqual(_copy_angle({}), 0.0)
        self.assertEqual(_copy_angle({"copyAngle": "none"}), 0.0)
        self.assertEqual(normalize_copy_settings({})["copyAngle"], "none")


if __name__ == "__main__":
    unittest.main()
