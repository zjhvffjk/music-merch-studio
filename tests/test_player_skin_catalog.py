import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

REPO = Path(__file__).resolve().parents[1]
ROOT = REPO / 'workbench/mini-mockup/player-skins'
sys.path.insert(0, str(REPO / 'tools'))
from make_player import make
from player_style import resolve_player_style


class PlayerSkinCatalogTests(unittest.TestCase):
    def test_every_registered_preview_is_local_and_present(self):
        catalog = json.loads((ROOT / 'catalog.json').read_text(encoding='utf-8'))
        self.assertEqual(len(catalog['skins']), 117)
        ids = [skin['id'] for skin in catalog['skins']]
        self.assertEqual(len(ids), len(set(ids)))
        for skin in catalog['skins']:
            with self.subTest(id=skin['id']):
                path = (ROOT / skin['preview']).resolve()
                self.assertTrue(path.is_relative_to(ROOT.resolve()))
                self.assertTrue(path.is_file())
                self.assertGreater(path.stat().st_size, 1000)

    def test_each_reference_is_linked_to_an_output_theme(self):
        catalog = json.loads((ROOT / 'catalog.json').read_text(encoding='utf-8'))
        self.assertEqual(catalog['usage'], 'renderable-reference')
        self.assertTrue(all(skin.get('outputTheme') for skin in catalog['skins']))
        self.assertIn('source', catalog)
        self.assertEqual(catalog['active_panel'], '播放器样式')

    def test_player_card_heart_is_filled_in_default_red_or_skin_accent(self):
        skin = resolve_player_style('nc_001')
        with TemporaryDirectory() as folder:
            cover = Path(folder) / 'cover.png'
            card = Path(folder) / 'card.png'
            Image.new('RGB', (100, 100), (51, 77, 97)).save(cover)
            for style, expected in ((None, (255, 45, 70)), (skin, skin.controls.accent)):
                with self.subTest(style=style):
                    make(cover, card, 'Track', 'Artist', 180, width=600, ratio=5 / 3,
                         player_style=style)
                    with Image.open(card) as rendered:
                        self.assertEqual(rendered.getpixel((418, 728)), expected)


if __name__ == '__main__':
    unittest.main()
