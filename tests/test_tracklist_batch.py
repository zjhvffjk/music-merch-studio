# -*- coding: utf-8 -*-
"""专辑详情页「勾选批量制作」：trackList 通道（run_artist 跳过歌手搜索）。"""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "workbench")]
import server


TRACKS = [
    {"id": 101, "name": "爱在西元前", "no": 1, "artist": "周杰伦",
     "album": "范特西", "dur": "03:54",
     "pic": "http://p1.music.126.net/a.jpg?param=800y800", "source": "163"},
    {"id": 102, "name": "简单爱", "no": 3, "artist": "周杰伦",
     "album": "范特西", "dur": "04:30",
     "pic": "http://p1.music.126.net/b.jpg?param=800y800", "source": "163"},
]


def _job():
    return {"log": [], "items": [], "skipped": [], "done": 0, "total": 0,
            "phase": "", "status": "running", "title": "", "error": None,
            "t0": 0.0, "elapsed": 0.0}


class TracklistPoolTests(unittest.TestCase):
    """前端专辑行（artist 字符串 / dur mm:ss 文本）→ render_song 规范池。"""

    def test_front_row_normalized(self):
        pool = server._tracklist_pool(TRACKS)
        self.assertEqual(pool[0]["name"], "爱在西元前")
        self.assertEqual(pool[0]["artists"], "周杰伦")
        self.assertEqual(pool[0]["dur_ms"], 234000)
        self.assertEqual(pool[1]["dur_ms"], 270000)
        self.assertEqual(pool[0]["source"], "163")

    def test_bad_rows_dropped_and_hms_parsed(self):
        pool = server._tracklist_pool([
            {"name": "  ", "id": 1},          # 空名丢弃
            {"name": "无声", "dur": "xx"},     # 解析不了 → 0
            {"name": "长歌", "dur": "1:02:03"},  # 时:分:秒 也支持
            "junk",                            # 非字典丢弃
        ])
        self.assertEqual([s["name"] for s in pool], ["无声", "长歌"])
        self.assertEqual(pool[0]["dur_ms"], 0)
        self.assertEqual(pool[1]["dur_ms"], 3723000)

    def test_non_list_gives_empty(self):
        self.assertEqual(server._tracklist_pool(None), [])
        self.assertEqual(server._tracklist_pool("x"), [])


class RunArtistTracklistTests(unittest.TestCase):
    """run_artist 收到 trackList 时不再搜索，逐首制作勾选曲目。"""

    def test_tracklist_skips_search_and_makes_all(self):
        made = [{"rank": 1, "name": "爱在西元前", "playerPath": "x"},
                {"rank": 2, "name": "简单爱", "playerPath": "y"}]
        job = _job()
        with patch.object(server, "pick_source",
                          side_effect=AssertionError("不应再搜索歌手")), \
             patch.object(server, "render_song",
                          side_effect=[(made[0], None), (made[1], None)]) as rs, \
             patch.object(server, "finish") as fin, \
             patch("time.sleep", lambda s: None):
            opt = dict(server.DEFAULTS)
            opt["trackList"] = TRACKS
            server.run_artist(job, opt)
        fin.assert_called_once()
        args = fin.call_args[0]
        self.assertEqual(args[2], "周杰伦")          # 收尾归属歌手
        self.assertIn("勾选2首", args[3])             # 收尾小标题
        self.assertEqual(job["total"], 2)
        self.assertEqual(job["done"], 2)
        self.assertEqual(job["items"], made)
        # 交给 render_song 的池是规范化后的曲目（artists/dur_ms）
        s0 = rs.call_args_list[0][0][1]
        self.assertEqual((s0["name"], s0["artists"], s0["dur_ms"]),
                         ("爱在西元前", "周杰伦", 234000))

    def test_empty_names_fail_without_search(self):
        job = _job()
        with patch.object(server, "pick_source",
                          side_effect=AssertionError("不应再搜索歌手")), \
             patch.object(server, "fail") as fl:
            opt = dict(server.DEFAULTS)
            opt["trackList"] = [{"name": "  ", "id": 1}]
            server.run_artist(job, opt)
        fl.assert_called_once()
        self.assertIn("没有可用数据", fl.call_args[0][1])

    def test_all_covers_failed_fails(self):
        job = _job()
        with patch.object(server, "pick_source",
                          side_effect=AssertionError("不应再搜索歌手")), \
             patch.object(server, "render_song", return_value=(None, "封面拿不到")), \
             patch.object(server, "fail") as fl, \
             patch("time.sleep", lambda s: None):
            opt = dict(server.DEFAULTS)
            opt["trackList"] = TRACKS
            server.run_artist(job, opt)
        fl.assert_called_once()
        self.assertIn("都没有可用封面", fl.call_args[0][1])
        self.assertEqual(job["skipped"], ["爱在西元前（封面拿不到）",
                                          "简单爱（封面拿不到）"])


if __name__ == "__main__":
    unittest.main()
