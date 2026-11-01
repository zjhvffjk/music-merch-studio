# -*- coding: utf-8 -*-
"""导出 ZIP 的落盘文件名：必须跟着「歌手-专辑名」走。

以前一律叫「迷你CD设计-<jid>」，下载一堆之后根本分不清哪个是哪张专辑
（2026-11-01 用户要求：名字对应歌手和专辑名，例如「郑润泽-旷野」）。
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "workbench"))
import design_service as DS


class ZipDownloadNameTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="zipname_")
        self.old = DS.OUT_DIR
        DS.OUT_DIR = Path(self.tmp)

    def tearDown(self):
        DS.OUT_DIR = self.old

    def _put(self, jid, meta):
        d = DS.OUT_DIR / jid
        d.mkdir(parents=True, exist_ok=True)
        (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")

    def test_artist_and_album(self):
        self._put("a1", {"kind": "minicd-design", "artist": "郑润泽", "album": "旷野"})
        self.assertEqual(DS.zip_download_name("a1"), "郑润泽-旷野.zip")

    def test_album_only(self):
        self._put("a2", {"kind": "minicd-design", "artist": "", "album": "旷野"})
        self.assertEqual(DS.zip_download_name("a2"), "旷野.zip")

    def test_fallback_when_both_missing(self):
        self._put("a3", {"kind": "minicd-design", "artist": "", "album": ""})
        self.assertEqual(DS.zip_download_name("a3"), "迷你CD设计-a3.zip")

    def test_illegal_chars_replaced(self):
        self._put("a4", {"kind": "minicd-design", "artist": "A/B", "album": "旷野: 2026?*"})
        name = DS.zip_download_name("a4")
        for ch in '\\/:*?"<>|':
            self.assertNotIn(ch, name)
        self.assertTrue(name.startswith("A_B-"))

    def test_batch_uses_singer_name(self):
        """同一位歌手的一整批 → 压缩包就叫他的名字，专辑在里面的文件夹里分。"""
        self._put("b1", {"kind": "minicd-design-batch", "artist": "郑润泽",
                         "count": 3,
                         "albums": [{"no": "01", "album": "旷野", "artist": "郑润泽"},
                                    {"no": "02", "album": "召唤", "artist": "郑润泽"}]})
        self.assertEqual(DS.zip_download_name("b1"), "郑润泽.zip")

    def test_batch_of_one(self):
        self._put("b3", {"kind": "minicd-design-batch", "artist": "周杰伦",
                         "count": 1,
                         "albums": [{"no": "01", "album": "范特西", "artist": "周杰伦"}]})
        self.assertEqual(DS.zip_download_name("b3"), "周杰伦.zip")

    def test_mixed_artists_keep_the_count_suffix(self):
        """混了好几位歌手 → 光写歌手名会误导，退回带张数的写法。"""
        self._put("b4", {"kind": "minicd-design-batch", "artist": "", "count": 4,
                         "albums": [{"no": "01", "album": "A", "artist": "甲"},
                                    {"no": "02", "album": "B", "artist": "乙"}]})
        name = DS.zip_download_name("b4")
        self.assertIn("批量4张", name)

    def test_batch_without_album_list_still_works(self):
        self._put("b2", {"kind": "minicd-design-batch", "artist": "郑润泽", "count": 3})
        self.assertEqual(DS.zip_download_name("b2"), "郑润泽.zip")

    def test_no_meta_falls_back_to_jid(self):
        self.assertEqual(DS.zip_download_name("ghost"), "迷你CD设计-ghost.zip")

    def test_bad_jid_is_safe(self):
        name = DS.zip_download_name("../../etc/passwd")
        self.assertNotIn("..", name)
        self.assertNotIn("/", name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
