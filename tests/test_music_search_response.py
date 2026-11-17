import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import fetch163
import make_album


class MusicSearchResponseTests(unittest.TestCase):
    def test_opaque_upstream_response_is_an_error_for_source_fallback(self):
        response = Mock(status_code=200, text='{"result":"opaque"}')
        response.json.return_value = {'result': 'opaque', 'code': 200}
        with patch.object(fetch163.S, 'get', return_value=response):
            data, error = fetch163.get_json_ex(fetch163.API + '/search/get/web', retry=1)
        self.assertEqual(data, {})
        self.assertIsNotNone(error)

    def test_opaque_search_response_uses_artist_suggestion(self):
        artist = {'id': 6452, 'name': '周杰伦'}
        def response(url, params=None, **kwargs):
            if '/search/get/web' in url:
                return {'result': 'opaque-server-response', 'code': 200}
            if '/search/suggest/web' in url:
                return {'result': {'artists': [artist]}}
            self.fail('Unexpected request: ' + url)
        albums = [{'id': 18888, 'name': '不能说的秘密', 'picUrl': 'https://example.com/cover.jpg'}]
        with patch.object(fetch163, 'get_json', side_effect=response), patch.object(fetch163, 'artist_albums', return_value=albums) as lookup:
            found, results = make_album.plan_albums('周杰伦', 2)
        self.assertEqual(found, artist)
        self.assertEqual(results[0]['id'], 18888)
        lookup.assert_called_once_with(6452, 400)

    def test_normal_search_results_remain_available(self):
        result = {'artists': [{'id': 6452}]}
        with patch.object(fetch163, 'get_json', return_value={'result': result}):
            self.assertEqual(fetch163.search('周杰伦', 'artist'), result)
