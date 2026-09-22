import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools")]
from title_typography import generate_artistic_typography, normalize_title_settings


def request_for(title):
    return {"album": title, "artist": "郑润泽", "visualDna": {"style": "handwritten", "mood": "dreamy"}}


class TitleTypographyTests(unittest.TestCase):
    def test_unconfigured_provider_never_claims_to_generate_art(self):
        result = generate_artistic_typography(request_for("如果呢"), "unavailable")
        self.assertEqual("unavailable", result["status"])
        self.assertEqual([], result["candidates"])

    def test_title_settings_default_to_cover_follow(self):
        self.assertEqual("cover-follow", normalize_title_settings({})["titleMode"])


if __name__ == "__main__":
    unittest.main()
