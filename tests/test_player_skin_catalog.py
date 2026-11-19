import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'workbench/mini-mockup/player-skins'


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


if __name__ == '__main__':
    unittest.main()
