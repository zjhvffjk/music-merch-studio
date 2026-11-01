# -*- coding: utf-8 -*-
"""批量导出 ZIP 的三层结构：歌手名.zip → 专辑文件夹 → 那一套素材。

以前批量下载下来是 01-disc.png / 02-cover.png 这种带序号的平铺文件名，
且每本只有 5 样东西，跟「单独生成一张专辑」出来的不一样 —— 用户还得自己
按编号分拣才知道哪个文件属于哪张专辑（2026-11-01 用户要求）。
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "workbench"))
import design_service as DS


def _touch(p):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"PNG")
    return p


class BatchAlbumFoldersTests(unittest.TestCase):
    def test_distinct_albums_use_their_own_name(self):
        rows = [{"no": "01", "album": "旷野"}, {"no": "02", "album": "召唤"}]
        self.assertEqual(DS._batch_album_folders(rows),
                         {"01": "旷野", "02": "召唤"})

    def test_duplicate_album_name_gets_a_suffix(self):
        rows = [{"no": "01", "album": "旷野"}, {"no": "02", "album": "旷野"},
                {"no": "03", "album": "旷野"}]
        folders = DS._batch_album_folders(rows)
        self.assertEqual(folders["01"], "旷野")
        self.assertEqual(folders["02"], "旷野 (2)")
        self.assertEqual(folders["03"], "旷野 (3)")

    def test_missing_album_name_falls_back_to_index(self):
        rows = [{"no": "07", "album": ""}, {"no": "08", "album": None}]
        self.assertEqual(DS._batch_album_folders(rows),
                         {"07": "专辑07", "08": "专辑08"})

    def test_illegal_chars_are_replaced(self):
        rows = [{"no": "01", "album": "A/B: 2026?"}]
        name = DS._batch_album_folders(rows)["01"]
        for ch in '\\/:*?"<>|':
            self.assertNotIn(ch, name)


class BatchZipPlanTests(unittest.TestCase):
    """包内的路径必须是「专辑文件夹/素材名」，不再是一堆带序号的平铺文件。"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="batchzip_"))
        self.rows = [{"no": "01", "album": "旷野", "artist": "郑润泽"},
                     {"no": "02", "album": "召唤", "artist": "郑润泽"}]

    def _fill(self, missing=()):
        for r in self.rows:
            no = r["no"]
            for f in DS._album_zip_members():
                if (no, f) in missing:
                    continue
                _touch(self.tmp / ("%s-%s" % (no, f)))
        _touch(self.tmp / DS.BATCH_SHEET)
        _touch(self.tmp / "meta.json")

    def _arcs(self):
        folders = DS._batch_album_folders(self.rows)
        plan = DS._batch_zip_plan(self.tmp, self.rows, folders, DS.BATCH_SHEET)
        return [arc for _src, arc in plan]

    def test_three_level_layout(self):
        self._fill()
        arcs = self._arcs()
        members = DS._album_zip_members()
        for r in self.rows:
            for f in members:
                self.assertIn("%s/%s" % (r["album"], f), arcs)
        self.assertIn(DS.BATCH_SHEET, arcs)
        self.assertIn("meta.json", arcs)

    def test_flat_numbered_names_are_gone(self):
        self._fill()
        for arc in self._arcs():
            top = arc.split("/")[0]
            self.assertFalse(top[:2].isdigit() and top[2:3] == "-",
                             "包内不该再出现 01- 这种平铺序号: %s" % arc)

    def test_each_album_gets_the_full_single_album_set(self):
        """每一本里面的东西必须跟「单独生成一张专辑」出来的完全一样。"""
        self._fill()
        members = list(DS._album_zip_members())
        self.assertEqual(len(members), 13)
        per_album = {}
        for arc in self._arcs():
            if "/" not in arc:
                continue
            folder, name = arc.split("/", 1)
            per_album.setdefault(folder, []).append(name)
        for _row in self.rows:
            self.assertEqual(sorted(per_album[_row["album"]]), sorted(members))

    def test_missing_file_skipped_not_failed(self):
        self._fill(missing={("01", "打印拼版-A4.pdf")})
        arcs = self._arcs()
        self.assertNotIn("旷野/打印拼版-A4.pdf", arcs)
        self.assertIn("召唤/打印拼版-A4.pdf", arcs)

    def test_disc_print_sheet_stays_out(self):
        """盘面拼版页不打包（2026-10-28 拍板），批量要跟单张一致。"""
        self._fill()
        for arc in self._arcs():
            self.assertNotIn("盘面拼版-A4", arc)


if __name__ == "__main__":
    unittest.main(verbosity=2)
