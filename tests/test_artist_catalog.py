import sys
import unittest
import threading
import urllib.request
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'workbench'))
import artist_catalog as catalog

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import server


class ArtistCatalogRoutesTests(unittest.TestCase):
    def test_browser_resources_are_served_with_correct_mime_types(self):
        service = server.Server(('127.0.0.1', 0), server.Handler)
        threading.Thread(target=service.serve_forever, daemon=True).start()
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            for path, mime in [('/artist-browser.js', 'javascript'), ('/artist-browser.css', 'text/css')]:
                with opener.open(f'http://127.0.0.1:{service.server_port}{path}') as response:
                    self.assertEqual(response.status, 200)
                    self.assertIn(mime, response.headers['Content-Type'])
        finally:
            service.shutdown()
            service.server_close()


class ArtistCatalogTests(unittest.TestCase):
    def setUp(self):
        catalog._CACHE.clear()

    def test_song_keeps_actual_performer_and_identity(self):
        song = catalog.song_brief({'id': 42, 'name': '作品', 'ar': [{'name': '演唱者'}],
            'al': {'id': 8, 'name': '专辑', 'picUrl': 'https://cover'}, 'dt': 185000})
        self.assertEqual((song['id'], song['artist'], song['albumId'], song['source']), (42, '演唱者', 8, '163'))
        self.assertEqual(song['dur'], '03:05')

    def test_artist_resolution_never_uses_qq_id_or_first_partial_match(self):
        with patch.object(catalog, '_get', return_value={'code':200, 'result': {'artists': [
            {'id': 11, 'name': '周杰伦翻唱'}, {'id': 6452, 'name': '周杰伦'}]}}):
            self.assertEqual(catalog.resolve_artist('周杰伦')['id'], 6452)

    def test_page_parameters_are_validated(self):
        for values in [(0, 50, 0), (7, 50, 0), (1, 101, 0), (1, 50, -1)]:
            with self.assertRaises(ValueError):
                catalog.works(6452, *values)

    def test_pagination_metadata_and_song_ids_survive(self):
        with patch.object(catalog, '_eapi', return_value={'code': 200, 'total': 130, 'more': True,
                'songs': [{'id': 42, 'name': '作品', 'ar': [{'name': '演唱者'}], 'al': {}}]}) as call:
            result = catalog.works(6452, 2, 50, 50)
            self.assertEqual(result['offset'], 50)
            self.assertEqual(result['total'], 130)
            self.assertEqual(result['songs'][0]['id'], 42)
            self.assertEqual(call.call_args.args[1]['offset'], 50)

    def test_upstream_errors_are_not_empty_success_or_cached(self):
        with patch.object(catalog, '_eapi', return_value={'code': -462}):
            with self.assertRaises(RuntimeError):
                catalog.works(6452, 3, 50, 0)
        self.assertFalse(catalog._CACHE)

    def test_empty_success_and_repeated_page_cached(self):
        with patch.object(catalog, '_eapi', return_value={'code': 200, 'total': 0, 'songs': [], 'more':False}) as call:
            result = catalog.works(6452, 6, 50, 0)
            self.assertEqual(result['songs'], [])
            self.assertEqual(catalog.works(6452, 6, 50, 0), result)
            self.assertEqual(call.call_count, 1)

    def test_profile_maps_banner_alias_and_counts(self):
        with patch.object(catalog, 'resolve_artist', return_value={'id': 6452}), \
             patch.object(catalog, '_get', return_value={'code':200, 'artist': {
                 'id':6452, 'name':'周杰伦', 'alias':['Jay Chou','周董'], 'briefDesc':'简介',
                 'musicSize':591, 'albumSize':49, 'mvSize':9, 'picUrl':'https://banner'}}):
            result = catalog.profile('周杰伦')
            self.assertEqual(result['artist']['id'], 6452)
            self.assertEqual(result['artist']['aliases'], ['Jay Chou','周董'])
            self.assertEqual(result['artist']['musicSize'], 591)


if __name__ == '__main__':
    unittest.main()
