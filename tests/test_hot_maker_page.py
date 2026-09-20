import re
import unittest
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / 'workbench' / 'index.html'


def hot_maker_source():
    html = PAGE.read_text(encoding='utf-8')
    match = re.search(r'function openHotMaker\(data\)\{([\s\S]*?)\n\}\n\n/\* 搜索结果', html)
    assert match, 'openHotMaker 未找到'
    return match.group(1)


class HotMakerPageTests(unittest.TestCase):
    def test_batch_page_has_song_style_output_and_detail_controls(self):
        source = hot_maker_source()
        self.assertIn('data-count="5"', source)
        self.assertIn('data-output="keychain"', source)
        self.assertIn('data-output="shop"', source)
        self.assertIn('data-output="vinyl"', source)
        self.assertIn('song-maker-details', source)
        self.assertIn('data-detail="playlist"', source)

    def test_batch_start_writes_selected_outputs_instead_of_forcing_all(self):
        source = hot_maker_source()
        self.assertIn("$('#p_keychain').checked=selected.keychain", source)
        self.assertIn("$('#p_shop').checked=selected.shop", source)
        self.assertIn("$('#p_vinyl').checked=selected.vinyl", source)
        self.assertIn("TOP=count", source)


if __name__ == '__main__':
    unittest.main()

class BatchPrintGalleryTests(unittest.TestCase):
    def test_batch_prints_use_downloadable_gallery_instead_of_full_size_stack(self):
        html = PAGE.read_text(encoding='utf-8')
        self.assertIn('function batchPrintGallery(d)', html)
        self.assertIn('class="batch-print-gallery"', html)
        self.assertIn('下载 PNG', html)
        self.assertIn('下载 PDF', html)
        self.assertIn("if(d.mode === 'artist' && ((d.playerPrints||[]).length", html)

class BatchPrintGalleryLayoutTests(unittest.TestCase):
    def test_preview_clips_paper_image_above_its_metadata(self):
        html = PAGE.read_text(encoding='utf-8')
        self.assertIn('.batch-print-card__preview{height:172px;padding:10px;overflow:hidden;', html)
        self.assertIn('max-height:152px', html)
