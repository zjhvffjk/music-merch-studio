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

    def test_each_spine_has_a_stable_template_default_and_invalid_values_fall_back(self):
        from copy_typography import normalize_copy_settings
        self.assertEqual(normalize_copy_settings({})["spineTemplates"],
                         {"right": "title-artist-classic", "left": "title-artist-classic", "leftBack": "title-artist-classic"})
        settings = normalize_copy_settings({"spineTemplates": {"right": "title-artist-classic", "left": "bad", "leftBack": "copy"}})
        self.assertEqual(settings["spineTemplates"],
                         {"right": "title-artist-classic", "left": "title-artist-classic", "leftBack": "title-artist-classic"})

    def test_custom_spine_text_is_kept_short_for_the_real_4_4mm_print_area(self):
        from copy_typography import normalize_copy_settings
        settings = normalize_copy_settings({"spineText": {"right": "这是超过十四个字的侧封自定义文字内容"}})
        self.assertEqual(len(settings["spineText"]["right"]), 14)

    def test_fixed_spine_template_uses_selected_text_color(self):
        from PIL import Image
        from design_parts import spine_overlay
        base = Image.new("RGB", (88, 760), "white")
        result = spine_overlay(base, "right", "ALBUM", "ARTIST", copy_settings={
            "spineAppearance": {"right": {"sizeMm": 1.7, "font": "auto", "style": "normal", "color": "#c8102e"}}
        })
        # 固定“标题+歌手”模板也必须使用工具栏中选择的红色，而不是只在自定义文字时生效。
        pixels = list(result.getdata())
        self.assertTrue(any(r > 130 and g < 55 and b < 80 for r, g, b in pixels))

    def test_spine_text_appearance_is_saved_per_physical_spine_with_safe_bounds(self):
        from copy_typography import normalize_copy_settings
        settings = normalize_copy_settings({"spineAppearance": {"right": {
            "font": "private:ygy_qianming.ttf", "sizeMm": 9, "style": "boldItalic", "color": "#C8102E"}}})
        appearance = settings["spineAppearance"]["right"]
        self.assertEqual(appearance["font"], "private:ygy_qianming.ttf")
        self.assertEqual(appearance["sizeMm"], 2.6)
        self.assertEqual(appearance["style"], "boldItalic")
        self.assertEqual(appearance["color"], "#c8102e")


if __name__ == "__main__":
    unittest.main()
