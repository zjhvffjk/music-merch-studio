import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "workbench"))

import fetch_qq
import server


class ArtistSourceSelectionTests(unittest.TestCase):
    def test_jay_chou_uses_stable_qq_singer_id_without_legacy_search(self):
        self.assertEqual(
            fetch_qq.search_singer_mid("周杰伦"),
            ("0025NhlN2yWrP4", "周杰伦"),
        )

    def test_low_quality_163_fallback_keeps_only_primary_artist_tracks(self):
        pool = [
            {"name": "合唱曲", "artists": "蔡依林/周杰伦"},
            {"name": "现场曲", "artists": "那英/周杰伦"},
            {"name": "主唱曲", "artists": "周杰伦/温岚"},
        ]
        with patch.object(server, "hot_songs_ex", return_value=({"id": 1, "name": "周杰伦"}, pool, None)), \
             patch.object(server, "search_singer_mid", side_effect=RuntimeError("QQ unavailable")):
            source, _, result, notes = server.pick_source("周杰伦", "auto", 20)

        self.assertEqual(source, "163")
        self.assertEqual([song["name"] for song in result], ["主唱曲"])
        self.assertTrue(any("仅保留网易云中主唱完全匹配" in note for note in notes))


if __name__ == "__main__":
    unittest.main()
