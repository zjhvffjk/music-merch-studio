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

class BatchDeliveryTests(unittest.TestCase):
    def test_completed_artist_batch_uses_fixed_delivery_shell(self):
        html = PAGE.read_text(encoding='utf-8')
        self.assertIn("d.mode === 'artist'", html)
        self.assertIn("const compactBatch = d.mode === 'artist'", html)
        self.assertIn("if((compactSingle || compactBatch)", html)
        self.assertIn("keychainOverview", html)
        self.assertIn("vinylOverview", html)




class BatchDeliveryResourceTests(unittest.TestCase):
    def test_batch_delivery_prefers_batch_overviews_and_keeps_all_print_sheets(self):
        source = hot_maker_source.__globals__['PAGE'].read_text(encoding='utf-8')
        self.assertIn("isBatch ? d.keychainOverview", source)
        self.assertIn("isBatch ? d.vinylOverview", source)
        self.assertIn("const prints=isBatch ? (d.playerPrints||[]) : (d.playerPrints||[]).slice(0,1)", source)
        self.assertIn("const foldPrints=isBatch ? (d.playerFoldPrints||[])", source)
