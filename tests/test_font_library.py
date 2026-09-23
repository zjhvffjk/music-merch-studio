import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools')]
import typo


class FontLibraryTests(unittest.TestCase):
    def test_selected_chinese_display_font_resolves_to_real_font_file(self):
        token = typo.set_font_overrides({'display': 'noto-serif-sc'})
        try:
            path = typo.resolved_font_path('serif', '如果呢')
        finally:
            typo.reset_font_overrides(token)
        self.assertTrue(path and Path(path).is_file())
        self.assertEqual('NotoSerifSC-VF.ttf', Path(path).name)

    def test_common_picker_presets_resolve_to_installed_files(self):
        for preset in ("fangsong", "simhei", "deng", "cambria", "ink-free", "segoe-print"):
            path = typo._preset_path(preset, "A")
            self.assertTrue(path and Path(path).is_file(), preset)

    def test_latin_font_is_not_used_for_chinese_text(self):
        token = typo.set_font_overrides({'display': 'georgia'})
        try:
            path = typo.resolved_font_path('serif', '如果呢')
        finally:
            typo.reset_font_overrides(token)
        self.assertNotEqual('georgia.ttf', Path(path).name.lower())

    def test_catalog_reads_the_real_local_font_library(self):
        catalog = typo.system_font_catalog()
        # 这是 Windows 主机的真实字体目录，不再局限于工作台的 18 个常用预设。
        self.assertGreaterEqual(len(catalog), 100)
        sample = catalog[0]
        self.assertTrue(sample['id'].startswith('system:'))
        self.assertTrue(Path(typo._system_font_file(sample['id'])).is_file())

    def test_builtin_open_font_is_available_without_windows_font_dependency(self):
        catalog = typo.builtin_font_catalog()
        self.assertGreaterEqual(len(catalog), 6)
        token = typo.set_font_overrides({'chineseCopy': 'builtin:noto-serif-sc'})
        try:
            path = typo.resolved_font_path('hand', '如果呢')
        finally:
            typo.reset_font_overrides(token)
        self.assertEqual('NotoSerifSC-wght.ttf', Path(path).name)

    def test_open_source_artistic_chinese_fonts_are_bundled(self):
        catalog = {row['id']: row for row in typo.builtin_font_catalog()}
        for font_id in ('builtin:ma-shan-zheng', 'builtin:zhi-mang-xing',
                        'builtin:liu-jian-mao-cao', 'builtin:long-cang'):
            self.assertIn(font_id, catalog)
            self.assertEqual('CJK', catalog[font_id]['language'])
            self.assertTrue((ROOT / 'assets' / catalog[font_id]['filename']).is_file())

    def test_selected_artist_font_resolves_to_real_file(self):
        token = typo.set_font_overrides({'artist': 'builtin:ma-shan-zheng'})
        try:
            path = typo.resolved_font_path('artist', '郑润泽')
        finally:
            typo.reset_font_overrides(token)
        self.assertEqual('MaShanZheng-Regular.ttf', Path(path).name)

    def test_selected_spine_font_resolves_to_real_file(self):
        token = typo.set_font_overrides({'spine': 'builtin:zhi-mang-xing'})
        try:
            path = typo.resolved_font_path('spine', '如果呢')
        finally:
            typo.reset_font_overrides(token)
        self.assertEqual('ZhiMangXing-Regular.ttf', Path(path).name)

    def test_selected_system_font_resolves_to_the_same_installed_file(self):
        catalog = typo.system_font_catalog()
        selected = next(x for x in catalog if x['filename'].lower() == 'arial.ttf')
        token = typo.set_font_overrides({'metadata': selected['id']})
        try:
            path = typo.resolved_font_path('num', '01 03:48')
        finally:
            typo.reset_font_overrides(token)
        self.assertEqual('arial.ttf', Path(path).name.lower())

    def test_private_font_directory_is_project_local_and_deployable(self):
        private_dir = typo.private_font_dir().resolve()
        self.assertEqual((ROOT / 'assets' / 'fonts' / 'personal').resolve(), private_dir)
        ignore = (ROOT / '.gitignore').read_text(encoding='utf-8')
        # 用户决定此工作台在另一台电脑也要带上同一套字体，因此个人字体目录
        # 是私有仓库的一部分，不能再被 .gitignore 排除。
        self.assertNotIn('/assets/fonts/personal/', ignore)
        self.assertGreaterEqual(len(typo.private_font_catalog()), 5)


if __name__ == '__main__':
    unittest.main()
