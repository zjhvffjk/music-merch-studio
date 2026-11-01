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

    def test_batch_uses_count(self):
        self._put("b1", {"kind": "minicd-design-batch", "artist": "郑润泽", "count": 5})
        self.assertEqual(DS.zip_download_name("b1"), "郑润泽-批量5张.zip")
        self._put("b2", {"kind": "minicd-design-batch", "artist": "", "count": 3})
        self.assertEqual(DS.zip_download_name("b2"), "批量3张.zip")

    def test_no_meta_falls_back_to_jid(self):
        self.assertEqual(DS.zip_download_name("ghost"), "迷你CD设计-ghost.zip")

    def test_bad_jid_is_safe(self):
        name = DS.zip_download_name("../../etc/passwd")
        self.assertNotIn("..", name)
        self.assertNotIn("/", name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
