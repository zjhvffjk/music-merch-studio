# -*- coding: utf-8 -*-
"""专辑详情页与歌手全部歌曲的后端映射（/api/album_songs、/api/artist_songs 的取数层）。"""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools")]
import fetch163


class AlbumSongsTests(unittest.TestCase):
    """fetch163.album_songs：v1 专辑接口 → 规范化曲目。"""

    def test_album_songs_normalization(self):
        alb = {"id": 18918, "name": "范特西", "picUrl": "http://p/p.jpg",
               "publishTime": 1000291200000, "company": "JVR", "type": "专辑"}
        raw = [{"id": 1, "name": "爱在西元前", "no": 2, "duration": 239027,
                "artists": [{"name": "周杰伦"}],
                "album": {"name": "范特西", "picUrl": "http://p/song.jpg"}},
               {"name": "", "id": 2},   # 空名条目应被丢弃
               {"id": 3, "name": "简单爱", "no": 4, "duration": 0,
                "artists": [], "album": {}}]
        with patch.object(fetch163, "get_json", return_value={"album": alb, "songs": raw}):
            info, songs = fetch163.album_songs(18918)
        self.assertEqual(info["name"], "范特西")
        self.assertEqual(info["company"], "JVR")
        self.assertEqual(len(songs), 2)                     # 空名被过滤
        self.assertEqual(songs[0]["name"], "爱在西元前")
        self.assertEqual(songs[0]["dur_ms"], 239027)
        self.assertEqual(songs[0]["artists"], "周杰伦")
        self.assertEqual(songs[0]["pic"], "http://p/song.jpg")  # 曲目封面优先
        self.assertEqual(songs[1]["pic"], "http://p/p.jpg")     # 缺失回退专辑封面
        self.assertEqual(songs[1]["album"], "范特西")

    def test_artist_top_songs_flattens_entries(self):
        hot = [{"id": 9, "name": "晴天", "duration": 269346,
                "artists": [{"name": "周杰伦"}],
                "album": {"name": "叶惠美", "picUrl": "http://p/y.jpg"}},
               {"song": {"id": 10, "name": "七里香", "duration": 1,
                         "artists": [{"name": "周杰伦"}], "album": {"name": "七里香"}}},
               {"name": ""}]
        with patch.object(fetch163, "get_json", return_value={"hotSongs": hot}):
            out = fetch163.artist_top_songs(6452, 50)
        self.assertEqual([s["name"] for s in out], ["晴天", "七里香"])
        self.assertEqual(out[0]["dur_ms"], 269346)
        self.assertEqual(out[1]["album"], "七里香")          # 嵌套 song 结构也兼容


if __name__ == "__main__":
    unittest.main()
