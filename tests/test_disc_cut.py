"""Disc artwork must stay within its physical cut in every export path."""

import sys
import unittest
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import design_parts as parts  # noqa: E402
import make_minicd as print_layout  # noqa: E402


class DiscCutTest(unittest.TestCase):
    def test_final_cut_masks_outer_edge_and_center_hole(self):
        artwork = Image.new("RGB", (400, 400), "#141e28")
        result = parts.clip_disc_to_cut(artwork, 50)
        self.assertEqual(result.size, (400, 400))
        self.assertEqual(result.getpixel((0, 0)), (255, 255, 255))
        self.assertEqual(result.getpixel((200, 200)), (255, 255, 255))
        self.assertEqual(result.getpixel((200, 100)), (20, 30, 40))

    def test_cutoff_cover_letter_is_repaired_without_blurring_the_disc(self):
        artwork = Image.new("RGB", (400, 400), "#141e28")
        ImageDraw.Draw(artwork).rectangle((193, 1, 207, 13), fill="white")
        repaired = parts._clean_generated_disc_edge(artwork)
        self.assertLess(max(repaired.getpixel((200, 5))), 100)
        self.assertEqual(repaired.getpixel((200, 100)), artwork.getpixel((200, 100)))

    def test_print_page_cuts_a_square_uploaded_disc(self):
        disc = Image.new("RGB", (100, 100), "black")
        page = print_layout.build_disc_page(disc, 64, cols=1, rows=1)
        x = print_layout.mm(10.0, 64)
        self.assertEqual(page.getpixel((x + 2, x + 2)), (255, 255, 255))


if __name__ == "__main__":
    unittest.main()
