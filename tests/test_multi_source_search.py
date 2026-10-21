# -*- coding: utf-8 -*-
"""多平台聚合搜索（QQ / 酷狗 / 网易云）与酷狗兜底链路。"""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "workbench")]
import fetch_kugou
import server


class KugouNormTests(unittest.TestCase):
    """酷狗两种条目（search/song 有 songname，singer/song 只有 filename）。"""

    def test_search_item_uses_songname(self):
        s = fetch_kugou._norm_song({"songname": "晴天", "singername": "周杰伦",
                                    "album_name": "叶惠美", "duration": 269,
                                    "album_audio_id": 1, "album_id": 2})
        self.assertEqual(s["name"], "晴天")
        self.assertEqual(s["artists"], "周杰伦")
        self.assertEqual(s["dur_ms"], 269000)
        self.assertEqual(s["source"], "kugou")
        self.assertEqual(s["album_id"], 2)

    def test_singer_item_parses_filename(self):
        s = fetch_kugou._norm_song({"filename": "周杰伦 - 晴天",
                                    "album_name": "叶惠美", "duration": 269})
        self.assertEqual((s["name"], s["artists"]), ("晴天", "周杰伦"))

    def test_album_cover_replaces_size_placeholder(self):
        with patch.object(fetch_kugou, "_j",
                          return_value={"data": {"imgurl":
                                      "http://imge.kugou.com/stdmusic/{size}/x.jpg"}}):
            self.assertEqual(fetch_kugou.album_cover_url(9, 480),
                             "http://imge.kugou.com/stdmusic/480/x.jpg")
        self.assertEqual(fetch_kugou.album_cover_url(None), "")


class MultiSearchTests(unittest.TestCase):
    """/api/song 与 /api/search 的聚合逻辑。"""

    def test_merge_dedup_and_priority(self):
        qq = [{"songname": "晴天", "singer": [{"name": "周杰伦", "mid": "m1"}],
               "albumname": "叶惠美", "interval": 269, "songid": 11, "albummid": "AM"}]
        kg = [{"name": "晴天", "artists": "周杰伦", "album": "叶惠美",
               "dur_ms": 269000, "id": 22, "album_id": 9, "hash": "h"},
              {"name": "简单爱", "artists": "周杰伦", "album": "范特西",
               "dur_ms": 240000, "id": 23, "album_id": 10, "hash": "h2"}]
        with patch.object(server, "search_song_q", return_value=qq), \
             patch.object(server, "search_song_kg", return_value=kg), \
             patch.object(server, "search", return_value={"songs": []}):
            out = server.multi_search_songs("晴天")
        # 同名去重：QQ 在前，酷狗只补没有的
        self.assertEqual([s["source"] for s in out], ["qq", "kugou"])
        self.assertEqual(out[0]["pic"], "https://y.gtimg.cn/music/photo_new/"
                                        "T002R800x800M000AM.jpg")
        self.assertEqual(out[1]["name"], "简单爱")   # 同名"晴天"被 QQ 去重掉了
        self.assertEqual(out[1]["albumId"], 10)
        self.assertEqual(out[1]["pic"], "")      # 酷狗封面生成时才懒解析

    def test_artists_exact_match_first(self):
        qq = [{"songname": "晴天", "singer": [{"name": "周杰伦", "mid": "m1"},
                                              {"name": "路人合唱", "mid": "m2"}],
               "albumname": "叶惠美", "interval": 1, "songid": 1, "albummid": "a"}]
        with patch.object(server, "search_song_q", return_value=qq), \
             patch.object(server, "search_singer_kg",
                          return_value=[{"id": 3520, "name": "周杰伦"},
                                        {"id": 9, "name": "蹭名周杰伦"}]), \
             patch.object(server, "search", return_value={"artists": []}):
            out = server.multi_search_artists("周杰伦")
        self.assertEqual(out[0]["name"], "周杰伦")
        self.assertEqual(out[0]["source"], "qq")
        self.assertEqual(out[0]["mid"], "m1")
        # 蹭名歌手（包含关系）保留但排后
        self.assertIn("蹭名周杰伦", [a["name"] for a in out])

    def test_artists_drops_unrelated_kugou_noise(self):
        """酷狗模糊结果只保留与查询词相关的，且精确命中排最前。"""
        with patch.object(server, "search_song_q", side_effect=RuntimeError("x")), \
             patch.object(server, "search_singer_kg",
                          return_value=[{"id": 1, "name": "完全无关的歌手"},
                                        {"id": 2, "name": "周杰伦"},
                                        {"id": 3, "name": "十分想见周杰伦"}]), \
             patch.object(server, "search", return_value={"artists": []}):
            out = server.multi_search_artists("周杰伦")
        names = [a["name"] for a in out]
        self.assertEqual(names[0], "周杰伦")            # 精确命中排最前
        self.assertNotIn("完全无关的歌手", names)        # 无关结果被丢弃
        self.assertLessEqual(len(names), 4)             # 蹭名结果有上限


class KugouFallbackTests(unittest.TestCase):
    """QQ/网易云都拿不到池子时，pick_source 应回落到酷狗。"""

    def test_pick_source_falls_back_to_kugou(self):
        kg_pool = [{"source": "kugou", "id": 1, "name": "温柔", "artists": "五月天",
                    "album": "自助系统", "album_id": 7, "dur_ms": 1000}]
        with patch.object(server, "hot_songs_ex",
                          return_value=(None, [], "限流")), \
             patch.object(server, "search_singer_mid",
                          side_effect=RuntimeError("qq down")), \
             patch.object(server, "search_singer_kg",
                          return_value=[{"id": 5, "name": "五月天"}]), \
             patch.object(server, "hot_songs_kg", return_value=kg_pool), \
             patch.object(server, "kugou_cover_url",
                          return_value="http://imge.kugou.com/stdmusic/480/x.jpg"):
            src, ar, pool, notes = server.pick_source("五月天", "auto", 3)
        self.assertEqual(src, "kugou")
        self.assertEqual(ar["name"], "五月天")
        self.assertEqual(pool[0]["pic"], "http://imge.kugou.com/stdmusic/480/x.jpg")

    def test_kugou_mode_skips_qq_and_163(self):
        with patch.object(server, "hot_songs_ex",
                          side_effect=AssertionError("163 should not run")), \
             patch.object(server, "search_singer_mid",
                          side_effect=AssertionError("qq should not run")), \
             patch.object(server, "search_singer_kg",
                          return_value=[{"id": 5, "name": "五月天"}]), \
             patch.object(server, "hot_songs_kg", return_value=[
                 {"source": "kugou", "id": 1, "name": "温柔", "artists": "五月天",
                  "album": "自助系统", "album_id": 7, "dur_ms": 1000}]), \
             patch.object(server, "kugou_cover_url", return_value=""):
            src, ar, pool, _ = server.pick_source("五月天", "kugou", 3)
        self.assertEqual(src, "kugou")
        self.assertEqual(pool[0]["name"], "温柔")


class AlbumSearchTests(unittest.TestCase):
    """专辑聚合搜索：/api/search 的 albums 字段。"""

    def test_albums_merge_dedup_and_cover(self):
        qa = [{"albummid": "AM", "albumid": 8217, "albumname": "范特西",
               "singer": "周杰伦", "date": "2001-09-14", "count": 10}]
        ka = [{"source": "kugou", "id": 958706, "name": "范特西",
               "singer": "周杰伦", "date": "2001-11-01", "count": 12,
               "pic": "http://imge.kugou.com/stdmusic/480/k.jpg"}]
        with patch.object(server, "search_album_q", return_value=qa), \
             patch.object(server, "search_album_kg", return_value=ka), \
             patch.object(server, "search", return_value={"albums": []}):
            out = server.multi_search_albums("范特西")
        # 同名同歌手去重：QQ 在前，酷狗不再重复
        self.assertEqual([a["source"] for a in out], ["qq"])
        self.assertEqual(out[0]["pic"], "https://y.gtimg.cn/music/photo_new/"
                                        "T002R800x800M000AM.jpg")
        self.assertEqual(out[0]["albummid"], "AM")

    def test_albums_survive_source_errors(self):
        with patch.object(server, "search_album_q", side_effect=RuntimeError("x")), \
             patch.object(server, "search_album_kg", side_effect=RuntimeError("y")), \
             patch.object(server, "search", return_value={"albums": [
                 {"id": 3, "name": "叶惠美", "artist": {"name": "周杰伦"},
                  "picUrl": "http://p1.music.126.net/x.jpg"}]}):
            out = server.multi_search_albums("叶惠美")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["source"], "163")
        self.assertEqual(out[0]["singer"], "周杰伦")

    def test_kugou_search_album_maps_fields(self):
        with patch.object(fetch_kugou, "_j",
                          return_value={"data": {"info": [
                              {"albumid": 958706, "albumname": "范特西",
                               "singername": "周杰伦", "publishtime": "2001-11-01",
                               "songcount": 12,
                               "imgurl": "http://imge.kugou.com/stdmusic/{size}/k.jpg"}]}}):
            out = fetch_kugou.search_album("范特西")
        self.assertEqual(out[0]["id"], 958706)
        self.assertEqual(out[0]["pic"], "http://imge.kugou.com/stdmusic/480/k.jpg")
        self.assertEqual(out[0]["count"], 12)


if __name__ == "__main__":
    unittest.main()
